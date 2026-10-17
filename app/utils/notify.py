"""Create in-app notifications for requisition changes. Callers commit the session."""
from app import db
from app.models import Notification, User


def active_users(**flags):
    """Active users matching flags, e.g. active_users(can_review=True)."""
    return User.query.filter_by(is_active=True, **flags).all()


def notify(users, message, requisition=None, category='info', exclude_id=None):
    seen = set()
    for user in users:
        if user is None or user.id in seen or user.id == exclude_id:
            continue
        seen.add(user.id)
        db.session.add(Notification(
            user_id=user.id,
            requisition_id=requisition.id if requisition is not None else None,
            message=message[:255],
            category=category,
        ))
