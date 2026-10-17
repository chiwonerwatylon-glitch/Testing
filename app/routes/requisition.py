from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Requisition, RequisitionItem, ApprovalLog, AuditLog, User
from app.utils.decorators import active_user_required, initiator_required, reviewer_required, approver_required
from app.utils.document_generator import RequisitionDocumentGenerator
from datetime import datetime
import os

requisition_bp = Blueprint('requisition', __name__)

@requisition_bp.route('/')
@requisition_bp.route('/dashboard')
@login_required
@active_user_required
def dashboard():
    # Get statistics
    stats = {
        'total_initiated': Requisition.query.filter_by(initiator_id=current_user.id).count(),
        'pending_review': Requisition.query.filter_by(status='pending_review').count() if current_user.can_review else 0,
        'pending_approval': Requisition.query.filter(
            Requisition.status.in_(['pending_approval', 'partially_approved'])
        ).count() if current_user.can_approve else 0,
        'approved': Requisition.query.filter_by(status='approved').count(),
    }
    
    # Recent requisitions
    if current_user.role == 'superuser':
        recent_requisitions = Requisition.query.order_by(Requisition.created_at.desc()).limit(10).all()
    else:
        recent_requisitions = Requisition.query.filter(
            (Requisition.initiator_id == current_user.id) |
            (Requisition.reviewer_id == current_user.id) |
            (Requisition.status.in_(['pending_approval', 'partially_approved']))
        ).order_by(Requisition.created_at.desc()).limit(10).all()
    
    return render_template('requisition/dashboard.html', stats=stats, recent_requisitions=recent_requisitions)

@requisition_bp.route('/create', methods=['GET', 'POST'])
@login_required
@active_user_required
@initiator_required
def create():
    if request.method == 'POST':
        # Check if user has signature
        if not current_user.signature_path:
            flash('You must upload your signature before creating a requisition. Please update your profile.', 'warning')
            return redirect(url_for('auth.profile'))
        
        # Create requisition
        requisition = Requisition(
            requisition_number=Requisition.generate_requisition_number(),
            in_favor_of=request.form.get('in_favor_of'),
            bank_name=request.form.get('bank_name'),
            branch=request.form.get('branch'),
            account_number=request.form.get('account_number'),
            reason_for_payment=request.form.get('reason_for_payment'),
            itf_263=request.form.get('itf_263', 'NA'),
            currency=request.form.get('currency', 'USD'),
            initiator_id=current_user.id,
            initiated_at=datetime.utcnow(),
            initiator_signature=current_user.signature_path,
            status='pending_review'
        )
        
        # Process items
        account_names = request.form.getlist('account_name[]')
        account_codes = request.form.getlist('account_code[]')
        account_locations = request.form.getlist('account_location[]')
        account_departments = request.form.getlist('account_department[]')
        details_list = request.form.getlist('details[]')
        debits = request.form.getlist('debit[]')
        credits = request.form.getlist('credit[]')
        
        total_debit = 0
        total_credit = 0
        
        for i in range(len(account_names)):
            if account_names[i] and account_codes[i]:
                debit = float(debits[i]) if debits[i] else 0
                credit = float(credits[i]) if credits[i] else 0
                
                item = RequisitionItem(
                    account_name=account_names[i],
                    account_code=account_codes[i],
                    account_location=account_locations[i] if i < len(account_locations) else '',
                    account_department=account_departments[i] if i < len(account_departments) else '',
                    details=details_list[i] if i < len(details_list) else '',
                    debit=debit,
                    credit=credit
                )
                requisition.items.append(item)
                total_debit += debit
                total_credit += credit
        
        requisition.total_debit = total_debit
        requisition.total_credit = total_credit
        requisition.required_approvals = requisition.calculate_required_approvals()
        
        db.session.add(requisition)
        
        # Audit log
        audit = AuditLog(
            user_id=current_user.id,
            action='create_requisition',
            entity_type='requisition',
            entity_id=requisition.id,
            details=f'Created requisition {requisition.requisition_number}',
            ip_address=request.remote_addr
        )
        db.session.add(audit)
        
        db.session.commit()
        
        flash(f'Requisition {requisition.requisition_number} created successfully and sent for review.', 'success')
        return redirect(url_for('requisition.detail', id=requisition.id))
    
    return render_template('requisition/create.html')

@requisition_bp.route('/list')
@login_required
@active_user_required
def list():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    
    query = Requisition.query
    
    # Filter based on user role
    if current_user.role != 'superuser':
        if current_user.can_review and current_user.can_approve:
            query = query.filter(
                (Requisition.initiator_id == current_user.id) |
                (Requisition.status == 'pending_review') |
                (Requisition.status.in_(['pending_approval', 'partially_approved']))
            )
        elif current_user.can_review:
            query = query.filter(
                (Requisition.initiator_id == current_user.id) |
                (Requisition.status == 'pending_review')
            )
        elif current_user.can_approve:
            query = query.filter(
                (Requisition.initiator_id == current_user.id) |
                (Requisition.status.in_(['pending_approval', 'partially_approved']))
            )
        else:
            query = query.filter_by(initiator_id=current_user.id)
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    requisitions = query.order_by(Requisition.created_at.desc()).paginate(page=page, per_page=20)
    
    return render_template('requisition/list.html', requisitions=requisitions, status_filter=status_filter)

@requisition_bp.route('/detail/<int:id>')
@login_required
@active_user_required
def detail(id):
    requisition = Requisition.query.get_or_404(id)
    
    # Get approval logs
    approval_logs = ApprovalLog.query.filter_by(requisition_id=id).order_by(ApprovalLog.approval_level).all()
    
    # Check pending approvals
    pending_approvals = []
    approved_levels = [log.approval_level for log in approval_logs if log.action == 'approved']
    
    for level in range(1, requisition.required_approvals + 1):
        if level not in approved_levels:
            pending_approvals.append(level)
    
    return render_template('requisition/detail.html', 
                          requisition=requisition, 
                          approval_logs=approval_logs,
                          pending_approvals=pending_approvals)

@requisition_bp.route('/print/<int:id>')
@login_required
@active_user_required
def print_view(id):
    requisition = Requisition.query.get_or_404(id)
    approval_logs = ApprovalLog.query.filter_by(requisition_id=id).order_by(ApprovalLog.approval_level).all()
    approved_levels = [log.approval_level for log in approval_logs if log.action == 'approved']
    pending_approvals = [lvl for lvl in range(1, requisition.required_approvals + 1) if lvl not in approved_levels]
    return render_template('requisition/print.html',
                           requisition=requisition,
                           approval_logs=approval_logs,
                           pending_approvals=pending_approvals)

@requisition_bp.route('/review/<int:id>', methods=['GET', 'POST'])
@login_required
@active_user_required
@reviewer_required
def review(id):
    requisition = Requisition.query.get_or_404(id)
    
    if requisition.status != 'pending_review':
        flash('This requisition is not pending review.', 'warning')
        return redirect(url_for('requisition.detail', id=id))
    
    if not current_user.signature_path:
        flash('You must upload your signature before reviewing. Please update your profile.', 'warning')
        return redirect(url_for('auth.profile'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        comments = request.form.get('comments', '')
        
        if action == 'approve':
            requisition.reviewer_id = current_user.id
            requisition.reviewed_at = datetime.utcnow()
            requisition.reviewer_signature = current_user.signature_path
            requisition.review_comments = comments
            requisition.status = 'pending_approval'
            
            flash('Requisition reviewed and approved. Sent to approvers.', 'success')
        elif action == 'reject':
            requisition.reviewer_id = current_user.id
            requisition.reviewed_at = datetime.utcnow()
            requisition.review_comments = comments
            requisition.status = 'rejected'
            
            flash('Requisition has been rejected.', 'info')
        
        # Audit log
        audit = AuditLog(
            user_id=current_user.id,
            action=f'review_{action}',
            entity_type='requisition',
            entity_id=requisition.id,
            details=f'Reviewed requisition {requisition.requisition_number}: {action}',
            ip_address=request.remote_addr
        )
        db.session.add(audit)
        db.session.commit()
        
        return redirect(url_for('requisition.detail', id=id))
    
    return render_template('requisition/review.html', requisition=requisition)

@requisition_bp.route('/approve/<int:id>', methods=['GET', 'POST'])
@login_required
@active_user_required
@approver_required
def approve(id):
    requisition = Requisition.query.get_or_404(id)
    
    if requisition.status not in ['pending_approval', 'partially_approved']:
        flash('This requisition is not pending approval.', 'warning')
        return redirect(url_for('requisition.detail', id=id))
    
    if not current_user.signature_path:
        flash('You must upload your signature before approving. Please update your profile.', 'warning')
        return redirect(url_for('auth.profile'))
    
    # Check if user already approved
    existing_approval = ApprovalLog.query.filter_by(
        requisition_id=id,
        approver_id=current_user.id,
        action='approved'
    ).first()
    
    if existing_approval:
        flash('You have already approved this requisition.', 'warning')
        return redirect(url_for('requisition.detail', id=id))
    
    # Determine approval level
    current_approvals = ApprovalLog.query.filter_by(
        requisition_id=id,
        action='approved'
    ).count()
    next_level = current_approvals + 1
    
    # Check if this is a senior approval (3rd level)
    if next_level == 3 and not current_user.is_senior_approver:
        flash('Only senior approvers can provide the third approval.', 'warning')
        return redirect(url_for('requisition.detail', id=id))
    
    if request.method == 'POST':
        action = request.form.get('action')
        comments = request.form.get('comments', '')
        
        approval_log = ApprovalLog(
            requisition_id=id,
            approver_id=current_user.id,
            approval_level=next_level,
            action=action,
            comments=comments,
            signature_path=current_user.signature_path
        )
        db.session.add(approval_log)
        
        if action == 'approved':
            requisition.current_approvals = next_level
            
            if next_level >= requisition.required_approvals:
                requisition.status = 'approved'
                requisition.completed_at = datetime.utcnow()
                flash('Requisition has been fully approved!', 'success')
            else:
                requisition.status = 'partially_approved'
                flash(f'Approval {next_level} of {requisition.required_approvals} completed.', 'success')
        else:
            requisition.status = 'rejected'
            flash('Requisition has been rejected.', 'info')
        
        # Audit log
        audit = AuditLog(
            user_id=current_user.id,
            action=f'approve_{action}',
            entity_type='requisition',
            entity_id=requisition.id,
            details=f'Approval level {next_level} for requisition {requisition.requisition_number}: {action}',
            ip_address=request.remote_addr
        )
        db.session.add(audit)
        db.session.commit()
        
        return redirect(url_for('requisition.detail', id=id))
    
    return render_template('requisition/approve.html', requisition=requisition, approval_level=next_level)

@requisition_bp.route('/download/<int:id>/<format>')
@login_required
@active_user_required
def download(id, format):
    requisition = Requisition.query.get_or_404(id)
    
    generator = RequisitionDocumentGenerator(requisition)
    
    if format == 'pdf':
        buffer = generator.generate_pdf()
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'{requisition.requisition_number}.pdf'
        )
    elif format == 'docx':
        buffer = generator.generate_docx()
        return send_file(
            buffer,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name=f'{requisition.requisition_number}.docx'
        )
    elif format == 'xlsx':
        buffer = generator.generate_excel()
        return send_file(
            buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'{requisition.requisition_number}.xlsx'
        )
    elif format == 'csv':
        buffer = generator.generate_csv()
        return send_file(
            buffer,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'{requisition.requisition_number}.csv'
        )
    else:
        flash('Invalid format requested.', 'danger')
        return redirect(url_for('requisition.detail', id=id))

@requisition_bp.route('/pending-review')
@login_required
@active_user_required
@reviewer_required
def pending_review():
    page = request.args.get('page', 1, type=int)
    requisitions = Requisition.query.filter_by(status='pending_review').order_by(
        Requisition.created_at.desc()
    ).paginate(page=page, per_page=20)
    
    return render_template('requisition/list.html', 
                          requisitions=requisitions, 
                          title='Pending Review',
                          status_filter='pending_review')

@requisition_bp.route('/pending-approval')
@login_required
@active_user_required
@approver_required
def pending_approval():
    page = request.args.get('page', 1, type=int)
    requisitions = Requisition.query.filter(
        Requisition.status.in_(['pending_approval', 'partially_approved'])
    ).order_by(Requisition.created_at.desc()).paginate(page=page, per_page=20)
    
    return render_template('requisition/list.html', 
                          requisitions=requisitions, 
                          title='Pending Approval',
                          status_filter='pending_approval')

@requisition_bp.route('/my-requisitions')
@login_required
@active_user_required
def my_requisitions():
    page = request.args.get('page', 1, type=int)
    requisitions = Requisition.query.filter_by(initiator_id=current_user.id).order_by(
        Requisition.created_at.desc()
    ).paginate(page=page, per_page=20)
    
    return render_template('requisition/list.html', 
                          requisitions=requisitions, 
                          title='My Requisitions')
