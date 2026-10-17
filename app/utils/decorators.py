from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

from flask import abort, flash, redirect, url_for
from flask_login import current_user

F = TypeVar("F", bound=Callable[..., Any])


def superuser_required(f: F) -> F:
    """Restrict a view to the admin (superuser) role.

    Anonymous users are sent to the login page; authenticated non-admin users
    receive a 403 response.
    """
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if current_user.role != "superuser":
            abort(403)
        return f(*args, **kwargs)

    return decorated_function  # type: ignore[return-value]


def reviewer_required(f: F) -> F:
    """Require the current user to have reviewer privileges."""
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any):
        if not current_user.is_authenticated or not current_user.can_review:
            flash(
                "You need reviewer privileges to access this page.",
                "danger",
            )
            return redirect(url_for("requisition.dashboard"))
        return f(*args, **kwargs)

    return decorated_function  # type: ignore[return-value]


def approver_required(f: F) -> F:
    """Require the current user to have approver privileges."""
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any):
        if not current_user.is_authenticated or not current_user.can_approve:
            flash(
                "You need approver privileges to access this page.",
                "danger",
            )
            return redirect(url_for("requisition.dashboard"))
        return f(*args, **kwargs)

    return decorated_function  # type: ignore[return-value]


def initiator_required(f: F) -> F:
    """Require the current user to have initiator privileges."""
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any):
        if not current_user.is_authenticated or not current_user.can_initiate:
            flash(
                "You need initiator privileges to access this page.",
                "danger",
            )
            return redirect(url_for("requisition.dashboard"))
        return f(*args, **kwargs)

    return decorated_function  # type: ignore[return-value]


def active_user_required(f: F) -> F:
    """Require the current user to be authenticated and marked active."""
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any):
        if not current_user.is_authenticated or not current_user.is_active:
            flash(
                "Your account is not yet activated. Please contact administrator.",
                "warning",
            )
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated_function  # type: ignore[return-value]
