from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app import db
from app.models import Requisition, User
from app.utils.decorators import active_user_required

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/requisitions/stats')
@login_required
@active_user_required
def requisition_stats():
    stats = {
        'draft': Requisition.query.filter_by(status='draft', initiator_id=current_user.id).count(),
        'pending_review': Requisition.query.filter_by(status='pending_review').count() if current_user.can_review else 0,
        'pending_approval': Requisition.query.filter(
            Requisition.status.in_(['pending_approval', 'partially_approved'])
        ).count() if current_user.can_approve else 0,
        'approved': Requisition.query.filter_by(status='approved').count(),
        'rejected': Requisition.query.filter_by(status='rejected').count(),
    }
    return jsonify(stats)

@api_bp.route('/requisition/<int:id>/status')
@login_required
@active_user_required
def requisition_status(id):
    requisition = Requisition.query.get_or_404(id)
    approval_status = requisition.get_approval_status()
    
    return jsonify({
        'requisition_number': requisition.requisition_number,
        'status': requisition.status,
        'approval_status': approval_status
    })

@api_bp.route('/users/reviewers')
@login_required
@active_user_required
def get_reviewers():
    reviewers = User.query.filter_by(can_review=True, is_active=True).all()
    return jsonify([{
        'id': r.id,
        'name': r.full_name,
        'department': r.department
    } for r in reviewers])

@api_bp.route('/users/approvers')
@login_required
@active_user_required
def get_approvers():
    approvers = User.query.filter_by(can_approve=True, is_active=True).all()
    return jsonify([{
        'id': a.id,
        'name': a.full_name,
        'department': a.department,
        'is_senior': a.is_senior_approver
    } for a in approvers])
