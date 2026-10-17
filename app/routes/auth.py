from __future__ import annotations

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
)
from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import generate_password_hash

from app import db
from app.models import User, AuditLog
from app.utils.helpers import save_signature

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Login page."""
    if current_user.is_authenticated:
        return redirect(url_for("requisition.dashboard"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        remember_raw = request.form.get("remember")
        remember = bool(remember_raw)  # checkbox -> True/False

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash(
                    "Your account is not yet activated. Please contact administrator.",
                    "warning",
                )
                return render_template("auth/login.html")

            login_user(user, remember=remember)

            audit = AuditLog(
                user_id=user.id,
                action="login",
                details="User logged in",
                ip_address=request.remote_addr,
                user_agent=(request.user_agent.string or "")[:255],
            )
            db.session.add(audit)
            db.session.commit()

            next_page = request.args.get("next")
            flash(f"Welcome back, {user.first_name}!", "success")
            return redirect(next_page or url_for("requisition.dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """User self-registration; requires admin activation afterward."""
    if current_user.is_authenticated:
        return redirect(url_for("requisition.dashboard"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        employee_id = (request.form.get("employee_id") or "").strip()
        department = (request.form.get("department") or "").strip()
        position = (request.form.get("position") or "").strip()
        phone = (request.form.get("phone") or "").strip()

        # Basic validation
        if not email or not password or not confirm_password:
            flash("Email and password fields are required.", "danger")
            return render_template("auth/register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("auth/register.html")

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return render_template("auth/register.html")

        if employee_id and User.query.filter_by(employee_id=employee_id).first():
            flash("Employee ID already registered.", "danger")
            return render_template("auth/register.html")

        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            employee_id=employee_id,
            department=department,
            position=position,
            phone=phone,
            password_hash=generate_password_hash(password),
            is_active=False,  # Needs admin approval
        )

        # Optional signature upload
        file = request.files.get("signature")
        if file and file.filename:
            signature_filename = save_signature(file, employee_id or email)
            if signature_filename:
                user.signature_path = signature_filename

        db.session.add(user)
        db.session.commit()

        flash(
            "Registration successful! Please wait for administrator approval.",
            "success",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    """Log out current user and record an audit log."""
    audit = AuditLog(
        user_id=current_user.id,
        action="logout",
        details="User logged out",
        ip_address=request.remote_addr,
        user_agent=(request.user_agent.string or "")[:255],
    )
    db.session.add(audit)
    db.session.commit()

    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """Profile page.

    Regular users may only change their own password here.
    Signature and all other profile fields are admin-managed
    (see admin.user_edit) and are deliberately ignored if submitted
    to this route.
    """
    if request.method == "POST":
        current_password = request.form.get("current_password") or ""
        new_password = request.form.get("new_password") or ""
        confirm_new_password = request.form.get("confirm_new_password") or ""

        if not current_password or not new_password or not confirm_new_password:
            flash(
                "Please fill in the current password, new password and confirmation.",
                "danger",
            )
            return render_template("auth/profile.html")

        if not current_user.check_password(current_password):
            flash("Current password is incorrect.", "danger")
            return render_template("auth/profile.html")

        if new_password != confirm_new_password:
            flash("New passwords do not match.", "danger")
            return render_template("auth/profile.html")

        current_user.set_password(new_password)

        audit = AuditLog(
            user_id=current_user.id,
            action="change_password",
            entity_type="user",
            entity_id=current_user.id,
            details="User changed their password",
            ip_address=request.remote_addr,
        )
        db.session.add(audit)
        db.session.commit()

        flash("Password updated successfully.", "success")
        return redirect(url_for("auth.profile"))

    return render_template("auth/profile.html")
