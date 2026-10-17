from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app import db
from app.models import User, Requisition, AuditLog
from app.utils.decorators import superuser_required
from app.utils.helpers import save_signature
from werkzeug.security import generate_password_hash
import os

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@login_required
@superuser_required
def dashboard():
    stats = {
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'pending_users': User.query.filter_by(is_active=False).count(),
        'total_requisitions': Requisition.query.count(),
        'pending_requisitions': Requisition.query.filter(
            Requisition.status.in_(['pending_review', 'pending_approval', 'partially_approved'])
        ).count(),
        'approved_requisitions': Requisition.query.filter_by(status='approved').count(),
    }
    
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_audits = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html', stats=stats, recent_users=recent_users, recent_audits=recent_audits)

@admin_bp.route('/users')
@login_required
@superuser_required
def users():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    
    query = User.query
    
    if search:
        query = query.filter(
            (User.first_name.ilike(f'%{search}%')) |
            (User.last_name.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%')) |
            (User.employee_id.ilike(f'%{search}%'))
        )
    
    if status_filter == 'active':
        query = query.filter_by(is_active=True)
    elif status_filter == 'inactive':
        query = query.filter_by(is_active=False)
    
    users = query.order_by(User.created_at.desc()).paginate(page=page, per_page=20)
    
    return render_template('admin/users.html', users=users, search=search, status_filter=status_filter)

@admin_bp.route('/user/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@superuser_required
def user_edit(id):
    user = User.query.get_or_404(id)
    
    if request.method == 'POST':
        user.first_name = request.form.get('first_name')
        user.last_name = request.form.get('last_name')
        user.department = request.form.get('department')
        user.position = request.form.get('position')
        user.phone = request.form.get('phone')
        user.role = request.form.get('role')
        user.is_active = request.form.get('is_active') == 'on'
        user.can_initiate = request.form.get('can_initiate') == 'on'
        user.can_review = request.form.get('can_review') == 'on'
        user.can_approve = request.form.get('can_approve') == 'on'
        user.is_senior_approver = request.form.get('is_senior_approver') == 'on'

        # Reviewers and approvers must never be initiators
        if user.can_review or user.can_approve or user.is_senior_approver:
            user.can_initiate = False

        
        # Reset password if requested
        new_password = request.form.get('new_password')
        if new_password:
            user.set_password(new_password)
        
        # Handle signature upload
        if 'signature' in request.files:
            file = request.files['signature']
            if file and file.filename:
                if user.signature_path:
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], user.signature_path)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                signature_filename = save_signature(file, user.employee_id)
                if signature_filename:
                    user.signature_path = signature_filename
        
        db.session.commit()
        
        # Audit log
        audit = AuditLog(
            user_id=current_user.id,
            action='update_user',
            entity_type='user',
            entity_id=user.id,
            details=f'Updated user {user.email}',
            ip_address=request.remote_addr
        )
        db.session.add(audit)
        db.session.commit()
        
        flash(f'User {user.full_name} updated successfully.', 'success')
        return redirect(url_for('admin.users'))
    
    return render_template('admin/user_edit.html', user=user)

@admin_bp.route('/user/<int:id>/activate', methods=['POST'])
@login_required
@superuser_required
def user_activate(id):
    user = User.query.get_or_404(id)
    user.is_active = True
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action='activate_user',
        entity_type='user',
        entity_id=user.id,
        details=f'Activated user {user.email}',
        ip_address=request.remote_addr
    )
    db.session.add(audit)
    db.session.commit()
    
    flash(f'User {user.full_name} has been activated.', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/user/<int:id>/deactivate', methods=['POST'])
@login_required
@superuser_required
def user_deactivate(id):
    user = User.query.get_or_404(id)
    
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'danger')
        return redirect(url_for('admin.users'))
    
    user.is_active = False
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action='deactivate_user',
        entity_type='user',
        entity_id=user.id,
        details=f'Deactivated user {user.email}',
        ip_address=request.remote_addr
    )
    db.session.add(audit)
    db.session.commit()
    
    flash(f'User {user.full_name} has been deactivated.', 'warning')
    return redirect(url_for('admin.users'))

@admin_bp.route('/user/create', methods=['GET', 'POST'])
@login_required
@superuser_required
def user_create():
    if request.method == 'POST':
        email = request.form.get('email')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('admin/user_edit.html', user=None)
        
        employee_id = request.form.get('employee_id')
        if User.query.filter_by(employee_id=employee_id).first():
            flash('Employee ID already registered.', 'danger')
            return render_template('admin/user_edit.html', user=None)
        
        user = User(
            email=email,
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            employee_id=employee_id,
            department=request.form.get('department'),
            position=request.form.get('position'),
            phone=request.form.get('phone'),
            role=request.form.get('role'),
            is_active=request.form.get('is_active') == 'on',
            can_initiate=request.form.get('can_initiate') == 'on',
            can_review=request.form.get('can_review') == 'on',
            can_approve=request.form.get('can_approve') == 'on',
            is_senior_approver=request.form.get('is_senior_approver') == 'on',
            password_hash=generate_password_hash(request.form.get('password'))
        )

        # Reviewers and approvers must never be initiators
        if user.can_review or user.can_approve or user.is_senior_approver:
            user.can_initiate = False

        
        # Handle signature upload
        if 'signature' in request.files:
            file = request.files['signature']
            if file and file.filename:
                signature_filename = save_signature(file, employee_id)
                if signature_filename:
                    user.signature_path = signature_filename
        
        db.session.add(user)
        
        # Audit log
        audit = AuditLog(
            user_id=current_user.id,
            action='create_user',
            entity_type='user',
            entity_id=user.id,
            details=f'Created user {user.email}',
            ip_address=request.remote_addr
        )
        db.session.add(audit)
        db.session.commit()
        
        flash(f'User {user.full_name} created successfully.', 'success')
        return redirect(url_for('admin.users'))
    
    return render_template('admin/user_edit.html', user=None)

@admin_bp.route('/audit-logs')
@login_required
@superuser_required
def audit_logs():
    page = request.args.get('page', 1, type=int)
    user_id = request.args.get('user_id', type=int)
    action = request.args.get('action', '')
    
    query = AuditLog.query
    
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    if action:
        query = query.filter(AuditLog.action.ilike(f'%{action}%'))
    
    logs = query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=50)
    users = User.query.all()
    
    return render_template('admin/audit_logs.html', logs=logs, users=users, 
                          selected_user_id=user_id, action_filter=action)
