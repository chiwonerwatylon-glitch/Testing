from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from app import db
from app.models import Requisition, User
from app.utils.decorators import active_user_required

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/requisitions/stats")
@login_required
@active_user_required
def requisition_stats():
    """Summary statistics for the current user's requisitions (and global queues)."""
    stats = {
        "draft": Requisition.query.filter_by(
            status="draft", initiator_id=current_user.id
        ).count(),
        "pending_review": (
            Requisition.query.filter_by(status="pending_review").count()
            if current_user.can_review
            else 0
        ),
        "pending_approval": (
            Requisition.query.filter(
                Requisition.status.in_(
                    ["pending_approval", "partially_approved"]
                )
            ).count()
            if current_user.can_approve
            else 0
        ),
        "approved": Requisition.query.filter_by(status="approved").count(),
        "rejected": Requisition.query.filter_by(status="rejected").count(),
    }
    return jsonify(stats)


@api_bp.route("/requisition/<int:id>/status")
@login_required
@active_user_required
def requisition_status(id: int):
    """Get status and approval state for a specific requisition."""
    requisition = Requisition.query.get_or_404(id)
    approval_status = requisition.get_approval_status()

    return jsonify(
        {
            "requisition_number": requisition.requisition_number,
            "status": requisition.status,
            "approval_status": approval_status,
        }
    )


@api_bp.route("/users/reviewers")
@login_required
@active_user_required
def get_reviewers():
    """List all active reviewers."""
    reviewers = User.query.filter_by(can_review=True, is_active=True).all()
    return jsonify(
        [
            {
                "id": reviewer.id,
                "name": reviewer.full_name,
                "department": reviewer.department,
            }
            for reviewer in reviewers
        ]
    )


@api_bp.route("/users/approvers")
@login_required
@active_user_required
def get_approvers():
    """List all active approvers with senior flag."""
    approvers = User.query.filter_by(can_approve=True, is_active=True).all()
    return jsonify(
        [
            {
                "id": approver.id,
                "name": approver.full_name,
                "department": approver.department,
                "is_senior": approver.is_senior_approver,
            }
            for approver in approvers
        ]
    )


@api_bp.route("/notifications")
@login_required
@active_user_required
def notifications():
    """Return recent notifications and unread count for current user."""
    from app.models import Notification  # kept here to avoid circular import

    notifications_query = current_user.notifications
    unread_count = notifications_query.filter_by(is_read=False).count()

    items = (
        notifications_query.order_by(Notification.created_at.desc())
        .limit(15)
        .all()
    )

    return jsonify(
        {
            "unread": unread_count,
            "items": [
                {
                    "id": n.id,
                    "message": n.message,
                    "category": n.category,
                    "is_read": n.is_read,
                    "requisition_id": n.requisition_id,
                    "created_at": (
                        n.created_at.strftime("%d %b %Y %H:%M")
                        if n.created_at
                        else ""
                    ),
                }
                for n in items
            ],
        }
    )


@api_bp.route("/notifications/read", methods=["POST"])
@login_required
@active_user_required
def notifications_read():
    """Mark all current user's notifications as read."""
    from app.models import Notification  # kept local intentionally

    Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).update({"is_read": True})
    db.session.commit()

    return jsonify({"ok": True})
