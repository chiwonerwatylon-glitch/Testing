from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from app import db
from app.models import User, AuditLog
from app.utils.helpers import save_signature
import os

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('requisition.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember', False)
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account is not yet activated. Please contact administrator.', 'warning')
                return render_template('auth/login.html')
            
            login_user(user, remember=remember)
            
            # Audit log
            audit = AuditLog(
                user_id=user.id,
                action='login',
                details='User logged in',
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string[:255]
            )
            db.session.add(audit)
            db.session.commit()
            
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.first_name}!', 'success')
            return redirect(next_page if next_page else url_for('requisition.dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('requisition.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        employee_id = request.form.get('employee_id')
        department = request.form.get('department')
        position = request.form.get('position')
        phone = request.form.get('phone')
        
        # Validation
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('auth/register.html')
        
        if User.query.filter_by(employee_id=employee_id).first():
            flash('Employee ID already registered.', 'danger')
            return render_template('auth/register.html')
        
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            employee_id=employee_id,
            department=department,
            position=position,
            phone=phone,
            password_hash=generate_password_hash(password),
            is_active=False  # Needs admin approval
        )
        
        # Handle signature upload
        if 'signature' in request.files:
            file = request.files['signature']
            if file and file.filename:
                signature_filename = save_signature(file, employee_id)
                if signature_filename:
                    user.signature_path = signature_filename
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please wait for administrator approval.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action='logout',
        details='User logged out',
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string[:255]
    )
    db.session.add(audit)
    db.session.commit()
    
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.phone = request.form.get('phone')
        current_user.position = request.form.get('position')
        
        # Handle signature upload
        if 'signature' in request.files:
            file = request.files['signature']
            if file and file.filename:
                # Delete old signature if exists
                if current_user.signature_path:
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_user.signature_path)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                signature_filename = save_signature(file, current_user.employee_id)
                if signature_filename:
                    current_user.signature_path = signature_filename
        
        # Handle password change
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_new_password = request.form.get('confirm_new_password')
        
        if current_password and new_password:
            if not current_user.check_password(current_password):
                flash('Current password is incorrect.', 'danger')
                return render_template('auth/profile.html')
            
            if new_password != confirm_new_password:
                flash('New passwords do not match.', 'danger')
                return render_template('auth/profile.html')
            
            current_user.set_password(new_password)
            flash('Password updated successfully.', 'success')
        
        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('auth/profile.html')
