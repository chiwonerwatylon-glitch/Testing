"""Create in-app notifications for requisition changes.

Callers are responsible for committing the session.
"""

from __future__ import annotations

from typing import Iterable, Optional

from app import db
from app.models import Notification, User


def active_users(**flags) -> list[User]:
    """Return active users matching the given flags.

    Example:
        active_users(can_review=True)
    """
    return User.query.filter_by(is_active=True, **flags).all()


def notify(
    users: Iterable[Optional[User]],
    message: str,
    requisition=None,
    category: str = "info",
    exclude_id: Optional[int] = None,
) -> None:
    """Create Notification rows for the given users.

    Args:
        users: Iterable of User objects (or None entries, which are ignored).
        message: Notification text (will be truncated to 255 characters).
        requisition: Optional requisition object to link to the notification.
        category: Category label (e.g. "info", "pending", "approved", "rejected").
        exclude_id: User ID to exclude from notifications (e.g. current user).

    Note:
        This function does NOT commit the session; callers must commit.
    """
    seen: set[int] = set()
    req_id = getattr(requisition, "id", None) if requisition is not None else None
    text = (message or "")[:255]

    for user in users:
        if not user or not getattr(user, "id", None):
            continue
        if user.id == exclude_id or user.id in seen:
            continue
        seen.add(user.id)
        db.session.add(
            Notification(
                user_id=user.id,
                requisition_id=req_id,
                message=text,
                category=category,
            )
        )
