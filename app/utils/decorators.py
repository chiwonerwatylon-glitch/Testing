from functools import wraps
from flask import redirect, url_for, flash, abort
from flask_login import current_user

def superuser_required(f):
    """Restrict a view to the admin (superuser) role.

    Anonymous users are sent to the login page; authenticated non-admin users
    receive a 403 response.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.role != 'superuser':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def reviewer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.can_review:
            flash('You need reviewer privileges to access this page.', 'danger')
            return redirect(url_for('requisition.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def approver_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.can_approve:
            flash('You need approver privileges to access this page.', 'danger')
            return redirect(url_for('requisition.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def initiator_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.can_initiate:
            flash('You need initiator privileges to access this page.', 'danger')
            return redirect(url_for('requisition.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def active_user_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_active:
            flash('Your account is not yet activated. Please contact administrator.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function
