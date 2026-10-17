from functools import wraps
from flask import redirect, url_for, flash, abort
from flask_login import current_user

def superuser_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'superuser':
            flash('You need superuser privileges to access this page.', 'danger')
            return redirect(url_for('requisition.dashboard'))
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
