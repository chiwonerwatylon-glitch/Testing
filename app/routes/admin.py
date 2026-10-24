from __future__ import annotations

import os

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app,
)
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

from app import db
from app.models import User, Requisition, AuditLog
from app.utils.decorators import superuser_required
from app.utils.helpers import save_signature

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/dashboard")
@login_required
@superuser_required
def dashboard():
    """Admin dashboard with system statistics."""
    stats = {
        "total_users": User.query.count(),
        "active_users": User.query.filter_by(is_active=True).count(),
        "pending_users": User.query.filter_by(is_active=False).count(),
        "total_requisitions": Requisition.query.count(),
        "pending_requisitions": Requisition.query.filter(
            Requisition.status.in_(
                ["pending_review", "pending_approval", "partially_approved"]
            )
        ).count(),
        "approved_requisitions": Requisition.query.filter_by(
            status="approved"
        ).count(),
    }

    recent_users = (
        User.query.order_by(User.created_at.desc()).limit(5).all()
    )
    recent_audits = (
        AuditLog.query.order_by(AuditLog.created_at.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_users=recent_users,
        recent_audits=recent_audits,
    )


@admin_bp.route("/users")
@login_required
@superuser_required
def users():
    """List users with search and status filter."""
    page = request.args.get("page", 1, type=int)
    search = (request.args.get("search") or "").strip()
    status_filter = (request.args.get("status") or "").strip()

    query = User.query

    if search:
        like = f"%{search}%"
        query = query.filter(
            (User.first_name.ilike(like))
            | (User.last_name.ilike(like))
            | (User.email.ilike(like))
            | (User.employee_id.ilike(like))
        )

    if status_filter == "active":
        query = query.filter_by(is_active=True)
    elif status_filter == "inactive":
        query = query.filter_by(is_active=False)

    users_page = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=20
    )

    return render_template(
        "admin/users.html",
        users=users_page,
        search=search,
        status_filter=status_filter,
    )


@admin_bp.route("/user/<int:id>/edit", methods=["GET", "POST"])
@login_required
@superuser_required
def user_edit(id: int):
    """Edit an existing user."""
    user = User.query.get_or_404(id)

    if request.method == "POST":
        user.first_name = (request.form.get("first_name") or "").strip()
        user.last_name = (request.form.get("last_name") or "").strip()
        user.department = (request.form.get("department") or "").strip()
        user.position = (request.form.get("position") or "").strip()
        user.phone = (request.form.get("phone") or "").strip()
        user.role = (request.form.get("role") or "").strip()

        user.is_active = request.form.get("is_active") == "on"
        user.can_initiate = request.form.get("can_initiate") == "on"
        user.can_review = request.form.get("can_review") == "on"
        user.can_approve = request.form.get("can_approve") == "on"
        user.is_senior_approver = (
            request.form.get("is_senior_approver") == "on"
        )

        # Reset password if provided
        new_password = (request.form.get("new_password") or "").strip()
        if new_password:
            user.set_password(new_password)

        # Handle signature upload
        file = request.files.get("signature")
        if file and file.filename:
            # Delete old signature file if it exists
            if user.signature_path:
                old_path = os.path.join(
                    current_app.config["UPLOAD_FOLDER"],
                    user.signature_path,
                )
                if os.path.exists(old_path):
                    os.remove(old_path)

            signature_filename = save_signature(file, user.employee_id)
            if signature_filename:
                user.signature_path = signature_filename

        db.session.add(user)
        db.session.flush()  # ensure user.id is available

        audit = AuditLog(
            user_id=current_user.id,
            action="update_user",
            entity_type="user",
            entity_id=user.id,
            details=f"Updated user {user.email}",
            ip_address=request.remote_addr,
        )
        db.session.add(audit)
        db.session.commit()

        flash(f"User {user.full_name} updated successfully.", "success")
        return redirect(url_for("admin.users"))

    return render_template("admin/user_edit.html", user=user)


@admin_bp.route("/user/<int:id>/activate", methods=["POST"])
@login_required
@superuser_required
def user_activate(id: int):
    """Activate a user account."""
    user = User.query.get_or_404(id)
    user.is_active = True

    db.session.add(user)
    db.session.flush()

    audit = AuditLog(
        user_id=current_user.id,
        action="activate_user",
        entity_type="user",
        entity_id=user.id,
        details=f"Activated user {user.email}",
        ip_address=request.remote_addr,
    )
    db.session.add(audit)
    db.session.commit()

    flash(f"User {user.full_name} has been activated.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/user/<int:id>/deactivate", methods=["POST"])
@login_required
@superuser_required
def user_deactivate(id: int):
    """Deactivate a user account (cannot deactivate self)."""
    user = User.query.get_or_404(id)

    if user.id == current_user.id:
        flash("You cannot deactivate your own account.", "danger")
        return redirect(url_for("admin.users"))

    user.is_active = False

    db.session.add(user)
    db.session.flush()

    audit = AuditLog(
        user_id=current_user.id,
        action="deactivate_user",
        entity_type="user",
        entity_id=user.id,
        details=f"Deactivated user {user.email}",
        ip_address=request.remote_addr,
    )
    db.session.add(audit)
    db.session.commit()

    flash(f"User {user.full_name} has been deactivated.", "warning")
    return redirect(url_for("admin.users"))


@admin_bp.route("/user/create", methods=["GET", "POST"])
@login_required
@superuser_required
def user_create():
    """Create a new user (admin-managed)."""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()

        if not email:
            flash("Email is required.", "danger")
            return render_template("admin/user_edit.html", user=None)

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return render_template("admin/user_edit.html", user=None)

        employee_id = (request.form.get("employee_id") or "").strip()
        if employee_id and User.query.filter_by(employee_id=employee_id).first():
            flash("Employee ID already registered.", "danger")
            return render_template("admin/user_edit.html", user=None)

        password = (request.form.get("password") or "").strip()
        if not password:
            flash("Password is required.", "danger")
            return render_template("admin/user_edit.html", user=None)

        user = User(
            email=email,
            first_name=(request.form.get("first_name") or "").strip(),
            last_name=(request.form.get("last_name") or "").strip(),
            employee_id=employee_id,
            department=(request.form.get("department") or "").strip(),
            position=(request.form.get("position") or "").strip(),
            phone=(request.form.get("phone") or "").strip(),
            role=(request.form.get("role") or "").strip(),
            is_active=request.form.get("is_active") == "on",
            can_initiate=request.form.get("can_initiate") == "on",
            can_review=request.form.get("can_review") == "on",
            can_approve=request.form.get("can_approve") == "on",
            is_senior_approver=(
                request.form.get("is_senior_approver") == "on"
            ),
            password_hash=generate_password_hash(password),
        )

        # Handle signature upload
        file = request.files.get("signature")
        if file and file.filename:
            signature_filename = save_signature(file, employee_id or email)
            if signature_filename:
                user.signature_path = signature_filename

        db.session.add(user)
        db.session.flush()  # ensure user.id is available

        audit = AuditLog(
            user_id=current_user.id,
            action="create_user",
            entity_type="user",
            entity_id=user.id,
            details=f"Created user {user.email}",
            ip_address=request.remote_addr,
        )
        db.session.add(audit)
        db.session.commit()

        flash(f"User {user.full_name} created successfully.", "success")
        return redirect(url_for("admin.users"))

    return render_template("admin/user_edit.html", user=None)


@admin_bp.route("/audit-logs")
@login_required
@superuser_required
def audit_logs():
    """Paginated audit logs with simple filters."""
    page = request.args.get("page", 1, type=int)
    user_id = request.args.get("user_id", type=int)
    action_filter = (request.args.get("action") or "").strip()

    query = AuditLog.query

    if user_id:
        query = query.filter_by(user_id=user_id)

    if action_filter:
        like = f"%{action_filter}%"
        query = query.filter(AuditLog.action.ilike(like))

    logs = query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=50
    )
    users = User.query.order_by(User.first_name, User.last_name).all()

    return render_template(
        "admin/audit_logs.html",
        logs=logs,
        users=users,
        selected_user_id=user_id,
        action_filter=action_filter,
    )


# ---------------------------------------------------------------------------
# Paying banks (the bank accounts initiators choose to pay from)
# ---------------------------------------------------------------------------

@admin_bp.route("/banks")
@login_required
@superuser_required
def banks():
    from app.models import PayingBank

    rows = PayingBank.query.order_by(
        PayingBank.bank_name, PayingBank.account_number
    ).all()
    return render_template("admin/banks.html", banks=rows)


@admin_bp.route("/banks/template")
@login_required
@superuser_required
def banks_template():
    from flask import send_file

    from app.utils.paying_banks import build_template

    return send_file(
        build_template(),
        mimetype=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        as_attachment=True,
        download_name="paying_banks_template.xlsx",
    )


@admin_bp.route("/banks/upload", methods=["POST"])
@login_required
@superuser_required
def banks_upload():
    from app.models import PayingBank
    from app.utils.paying_banks import parse_upload

    f = request.files.get("file")
    if not f or not f.filename:
        flash("Choose the filled-in Excel template to upload.", "warning")
        return redirect(url_for("admin.banks"))

    rows, errors = parse_upload(f)
    if errors:
        for e in errors[:10]:
            flash(e, "danger")
        flash("Nothing was imported. Fix the file and upload again.", "warning")
        return redirect(url_for("admin.banks"))

    added = updated = 0
    for r in rows:
        bank = PayingBank.query.filter_by(
            bank_name=r["bank_name"], account_number=r["account_number"]
        ).first()
        if bank:
            bank.account_name = r["account_name"]
            bank.currency_code = r["currency_code"]
            bank.is_active = True
            updated += 1
        else:
            db.session.add(PayingBank(**r))
            added += 1
    db.session.add(
        AuditLog(
            user_id=current_user.id,
            action="upload_paying_banks",
            entity_type="paying_bank",
            details=f"Uploaded paying banks: {added} added, {updated} updated",
            ip_address=request.remote_addr,
        )
    )
    db.session.commit()
    flash(f"Paying banks imported: {added} added, {updated} updated.", "success")
    return redirect(url_for("admin.banks"))


@admin_bp.route("/banks/<int:id>/toggle", methods=["POST"])
@login_required
@superuser_required
def banks_toggle(id: int):
    from app.models import PayingBank

    bank = PayingBank.query.get_or_404(id)
    bank.is_active = not bank.is_active
    db.session.add(
        AuditLog(
            user_id=current_user.id,
            action="toggle_paying_bank",
            entity_type="paying_bank",
            entity_id=bank.id,
            details=f"{bank.label} {'enabled' if bank.is_active else 'disabled'}",
            ip_address=request.remote_addr,
        )
    )
    db.session.commit()
    return redirect(url_for("admin.banks"))


# ---------------------------------------------------------------------------
# Account list (drop-downs for Account Name, Account Code and Location)
# ---------------------------------------------------------------------------

@admin_bp.route("/accounts")
@login_required
@superuser_required
def accounts():
    from app.models import AccountEntry

    rows = AccountEntry.query.order_by(
        AccountEntry.account_name, AccountEntry.account_code
    ).all()
    return render_template("admin/accounts.html", accounts=rows)


@admin_bp.route("/accounts/template")
@login_required
@superuser_required
def accounts_template():
    from flask import send_file

    from app.utils.account_codes import build_template

    return send_file(
        build_template(),
        mimetype=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        as_attachment=True,
        download_name="accounts_template.xlsx",
    )


@admin_bp.route("/accounts/upload", methods=["POST"])
@login_required
@superuser_required
def accounts_upload():
    from app.models import AccountEntry
    from app.utils.account_codes import parse_upload

    f = request.files.get("file")
    if not f or not f.filename:
        flash("Choose the filled-in Excel template to upload.", "warning")
        return redirect(url_for("admin.accounts"))

    rows, errors = parse_upload(f)
    if errors:
        for e in errors[:10]:
            flash(e, "danger")
        flash("Nothing was imported. Fix the file and upload again.", "warning")
        return redirect(url_for("admin.accounts"))

    # The uploaded file becomes the full list used in the drop-downs
    # (existing requisitions keep their own saved values).
    removed = AccountEntry.query.delete()
    for r in rows:
        db.session.add(AccountEntry(**r))
    db.session.add(
        AuditLog(
            user_id=current_user.id,
            action="upload_accounts",
            entity_type="account_entry",
            details=f"Uploaded account list: {len(rows)} rows replaced {removed}",
            ip_address=request.remote_addr,
        )
    )
    db.session.commit()
    flash(f"Account list replaced: {len(rows)} accounts loaded.", "success")
    return redirect(url_for("admin.accounts"))


# ---------------------------------------------------------------------------
# Payment reversals (initiator asked for a Paid requisition to go back to Not Paid)
# ---------------------------------------------------------------------------

@admin_bp.route("/payment-reversals")
@login_required
@superuser_required
def payment_reversals():
    from app.models import Requisition

    rows = (
        Requisition.query.filter(
            Requisition.payment_status == "paid",
            Requisition.reversal_requested_at.isnot(None),
        )
        .order_by(Requisition.reversal_requested_at)
        .all()
    )
    return render_template("admin/payment_reversals.html", requisitions=rows)


@admin_bp.route("/payment-reversals/<int:id>/mark-not-paid", methods=["POST"])
@login_required
@superuser_required
def mark_not_paid(id: int):
    from datetime import datetime

    from app.models import Requisition
    from app.utils.notify import notify

    requisition = Requisition.query.get_or_404(id)
    if not (requisition.is_paid and requisition.reversal_requested_at):
        flash("There is no pending reversal request for this requisition.", "warning")
        return redirect(url_for("admin.payment_reversals"))

    note = (request.form.get("note") or "").strip()
    reason = requisition.reversal_reason or ""
    if note:
        reason = f"{reason}\nAdmin note: {note}".strip()
    requisition.payment_status = "not_paid"
    requisition.unpaid_reason = reason
    requisition.unpaid_at = datetime.utcnow()
    requisition.unpaid_by_id = current_user.id
    requisition.reversal_reason = None
    requisition.reversal_requested_at = None
    db.session.add(
        AuditLog(
            user_id=current_user.id,
            action="mark_not_paid",
            entity_type="requisition",
            entity_id=requisition.id,
            details=f"{requisition.requisition_number} set back to Not Paid: {reason[:200]}",
            ip_address=request.remote_addr,
        )
    )
    notify(
        [requisition.initiator],
        f"{requisition.requisition_number} was set back to Not Paid. Mark it Paid again once it has been paid.",
        requisition,
        "update",
        exclude_id=current_user.id,
    )
    db.session.commit()
    flash(f"{requisition.requisition_number} set back to Not Paid.", "success")
    return redirect(url_for("admin.payment_reversals"))
