from __future__ import annotations

from datetime import datetime, timedelta

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    send_file,
    jsonify,
)
from flask_login import login_required, current_user

from app import db
from app.models import (
    Requisition,
    RequisitionItem,
    ApprovalLog,
    AuditLog,
    User,
)
from app.utils.decorators import (
    active_user_required,
    initiator_required,
    reviewer_required,
    approver_required,
)
from app.utils.document_generator import RequisitionDocumentGenerator
from app.utils.notify import notify, active_users
from app.utils.supporting_docs import merge_with_documents, save_supporting_documents

requisition_bp = Blueprint("requisition", __name__)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@requisition_bp.route("/")
@requisition_bp.route("/dashboard")
@login_required
@active_user_required
def dashboard():
    """User dashboard with summary stats and recent requisitions."""
    stats = {
        "total_initiated": Requisition.query.filter_by(
            initiator_id=current_user.id
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
    }

    if current_user.role == "superuser":
        recent_requisitions = (
            Requisition.query.order_by(Requisition.created_at.desc())
            .limit(10)
            .all()
        )
    else:
        recent_requisitions = (
            Requisition.query.filter(
                (Requisition.initiator_id == current_user.id)
                | (Requisition.reviewer_id == current_user.id)
                | Requisition.status.in_(
                    ["pending_approval", "partially_approved"]
                )
            )
            .order_by(Requisition.created_at.desc())
            .limit(10)
            .all()
        )

    return render_template(
        "requisition/dashboard.html",
        stats=stats,
        recent_requisitions=recent_requisitions,
    )


# ---------------------------------------------------------------------------
# Create requisition
# ---------------------------------------------------------------------------

@requisition_bp.route("/create", methods=["GET", "POST"])
@login_required
@active_user_required
@initiator_required
def create():
    """Create a new requisition."""
    if request.method == "POST":
        if not current_user.signature_path:
            flash(
                "You must upload your signature before creating a requisition. "
                "Please update your profile.",
                "warning",
            )
            return redirect(url_for("auth.profile"))

        requisition = Requisition(
            requisition_number=Requisition.generate_requisition_number(),
            in_favor_of=request.form.get("in_favor_of"),
            bank_name=request.form.get("bank_name"),
            branch=request.form.get("branch"),
            account_number=request.form.get("account_number"),
            reason_for_payment=request.form.get("reason_for_payment"),
            itf_263=request.form.get("itf_263", "NA"),
            currency=request.form.get("currency", "USD"),
            initiator_id=current_user.id,
            initiated_at=datetime.utcnow(),
            initiator_signature=current_user.signature_path,
            status="pending_review",
        )

        account_names = request.form.getlist("account_name[]")
        account_codes = request.form.getlist("account_code[]")
        account_locations = request.form.getlist("account_location[]")
        account_departments = request.form.getlist("account_department[]")
        details_list = request.form.getlist("details[]")
        debits = request.form.getlist("debit[]")
        credits = request.form.getlist("credit[]")

        total_debit = 0.0
        total_credit = 0.0

        for i in range(len(account_names)):
            if not (account_names[i] and account_codes[i]):
                continue

            debit = float(debits[i]) if debits[i] else 0.0
            credit = float(credits[i]) if credits[i] else 0.0

            item = RequisitionItem(
                account_name=account_names[i],
                account_code=account_codes[i],
                account_location=account_locations[i]
                if i < len(account_locations)
                else "",
                account_department=account_departments[i]
                if i < len(account_departments)
                else "",
                details=details_list[i] if i < len(details_list) else "",
                debit=debit,
                credit=credit,
            )
            requisition.items.append(item)
            total_debit += debit
            total_credit += credit

        requisition.total_debit = total_debit
        requisition.total_credit = total_credit
        requisition.required_approvals = requisition.calculate_required_approvals()

        db.session.add(requisition)
        db.session.flush()  # ensure requisition.id is available

        try:
            save_supporting_documents(
                requisition, request.files.getlist("supporting_documents")
            )
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return redirect(url_for("requisition.create"))

        audit = AuditLog(
            user_id=current_user.id,
            action="create_requisition",
            entity_type="requisition",
            entity_id=requisition.id,
            details=f"Created requisition {requisition.requisition_number}",
            ip_address=request.remote_addr,
        )
        db.session.add(audit)

        notify(
            active_users(can_review=True),
            f"{requisition.requisition_number} from {current_user.full_name} is awaiting review.",
            requisition,
            "pending",
            exclude_id=current_user.id,
        )
        db.session.commit()

        flash(
            f"Requisition {requisition.requisition_number} created successfully and sent for review.",
            "success",
        )
        return redirect(url_for("requisition.detail", id=requisition.id))

    reviewers = User.query.filter_by(can_review=True, is_active=True).all()
    approvers = User.query.filter_by(can_approve=True, is_active=True).all()
    senior_approvers = User.query.filter_by(
        is_senior_approver=True, is_active=True
    ).all()

    return render_template(
        "requisition/create.html",
        reviewers=reviewers,
        approvers=approvers,
        senior_approvers=senior_approvers,
    )


# ---------------------------------------------------------------------------
# List & detail views
# ---------------------------------------------------------------------------

def _base_requisition_query_for_user():
    """Base query filtered by user capabilities (except superuser)."""
    query = Requisition.query
    if current_user.role == "superuser":
        return query

    if current_user.can_review and current_user.can_approve:
        return query.filter(
            (Requisition.initiator_id == current_user.id)
            | (Requisition.status == "pending_review")
            | Requisition.status.in_(
                ["pending_approval", "partially_approved"]
            )
        )
    if current_user.can_review:
        return query.filter(
            (Requisition.initiator_id == current_user.id)
            | (Requisition.status == "pending_review")
        )
    if current_user.can_approve:
        return query.filter(
            (Requisition.initiator_id == current_user.id)
            | Requisition.status.in_(
                ["pending_approval", "partially_approved"]
            )
        )
    return query.filter_by(initiator_id=current_user.id)


@requisition_bp.route("/list")
@login_required
@active_user_required
def list():
    """Paginated listing with optional status filter."""
    page = request.args.get("page", 1, type=int)
    status_filter = (request.args.get("status") or "").strip()

    query = _base_requisition_query_for_user()
    if status_filter:
        query = query.filter_by(status=status_filter)

    requisitions = query.order_by(Requisition.created_at.desc()).paginate(
        page=page, per_page=20
    )

    return render_template(
        "requisition/list.html",
        requisitions=requisitions,
        status_filter=status_filter,
    )


@requisition_bp.route("/detail/<int:id>")
@login_required
@active_user_required
def detail(id: int):
    """Detailed requisition view with approval workflow status."""
    requisition = Requisition.query.get_or_404(id)

    approval_logs = (
        ApprovalLog.query.filter_by(requisition_id=id)
        .order_by(ApprovalLog.approval_level)
        .all()
    )

    approved_levels = [
        log.approval_level
        for log in approval_logs
        if log.action == "approved"
    ]
    pending_approvals = [
        level
        for level in range(1, requisition.required_approvals + 1)
        if level not in approved_levels
    ]

    from app.utils.workflow import build_workflow

    workflow = build_workflow(requisition, approval_logs)

    return render_template(
        "requisition/detail.html",
        requisition=requisition,
        approval_logs=approval_logs,
        pending_approvals=pending_approvals,
        workflow=workflow,
    )


# ---------------------------------------------------------------------------
# Verification & printing
# ---------------------------------------------------------------------------

def _document_code(
    requisition: Requisition, approval_logs: list[ApprovalLog]
) -> str:
    """Tamper-evident document code derived from key fields and approvals."""
    import hashlib

    fingerprint = "|".join(
        [
            str(requisition.requisition_number),
            str(requisition.total_debit),
            str(requisition.total_credit),
            str(requisition.currency),
            str(requisition.status),
            str(requisition.current_approvals),
            ",".join(
                f"{log.approver_id}:{log.approval_level}:{log.action}"
                for log in approval_logs
            ),
        ]
    )
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest().upper()
    # First 16 hex chars grouped by 4 (4-4-4-4)
    return "-".join(digest[i : i + 4] for i in range(0, 16, 4))


@requisition_bp.route("/verify/<int:id>")
@login_required
@active_user_required
def verify(id: int):
    """Return verification info and document code for a requisition."""
    requisition = Requisition.query.get_or_404(id)
    approval_logs = (
        ApprovalLog.query.filter_by(requisition_id=id)
        .order_by(ApprovalLog.approval_level)
        .all()
    )

    return jsonify(
        {
            "requisition_number": requisition.requisition_number,
            "status": requisition.status,
            "document_code": _document_code(requisition, approval_logs),
        }
    )


@requisition_bp.route("/print/<int:id>")
@login_required
@active_user_required
def print_view(id: int):
    """Print-friendly view, including QR code for verification URL."""
    requisition = Requisition.query.get_or_404(id)
    approval_logs = (
        ApprovalLog.query.filter_by(requisition_id=id)
        .order_by(ApprovalLog.approval_level)
        .all()
    )

    approved_levels = [
        log.approval_level
        for log in approval_logs
        if log.action == "approved"
    ]
    pending_approvals = [
        level
        for level in range(1, requisition.required_approvals + 1)
        if level not in approved_levels
    ]

    signature_code = _document_code(requisition, approval_logs)
    verify_url = url_for("requisition.verify", id=requisition.id, _external=True)

    qr = None
    try:
        import base64
        import io
        import qrcode

        img = qrcode.make(verify_url or signature_code)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        qr = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(
            "ascii"
        )
    except Exception:
        qr = None

    return render_template(
        "requisition/print.html",
        requisition=requisition,
        approval_logs=approval_logs,
        pending_approvals=pending_approvals,
        qr=qr,
        signature_code=signature_code,
        verify_url=verify_url,
        printed_at=datetime.utcnow(),
        printed_by=current_user.full_name,
    )


# ---------------------------------------------------------------------------
# Review & approval
# ---------------------------------------------------------------------------

@requisition_bp.route("/review/<int:id>", methods=["GET", "POST"])
@login_required
@active_user_required
@reviewer_required
def review(id: int):
    requisition = Requisition.query.get_or_404(id)

    if requisition.status != "pending_review":
        flash("This requisition is not pending review.", "warning")
        return redirect(url_for("requisition.detail", id=id))

    if not current_user.signature_path:
        flash(
            "You must upload your signature before reviewing. "
            "Please update your profile.",
            "warning",
        )
        return redirect(url_for("auth.profile"))

    if request.method == "POST":
        action = request.form.get("action")
        comments = request.form.get("comments", "")

        requisition.reviewer_id = current_user.id
        requisition.reviewed_at = datetime.utcnow()
        requisition.review_comments = comments

        if action == "approve":
            requisition.reviewer_signature = current_user.signature_path
            requisition.status = "pending_approval"
            flash(
                "Requisition reviewed and approved. Sent to approvers.",
                "success",
            )

            notify(
                active_users(can_approve=True),
                f"{requisition.requisition_number} was reviewed and is awaiting approval.",
                requisition,
                "pending",
                exclude_id=current_user.id,
            )
            notify(
                [requisition.initiator],
                f"{requisition.requisition_number} passed review and was sent for approval.",
                requisition,
                "update",
            )
        else:
            requisition.status = "rejected"
            flash("Requisition has been rejected.", "info")

            notify(
                [requisition.initiator],
                f"{requisition.requisition_number} was rejected at review.",
                requisition,
                "rejected",
            )

        audit = AuditLog(
            user_id=current_user.id,
            action=f"review_{action}",
            entity_type="requisition",
            entity_id=requisition.id,
            details=(
                f"Reviewed requisition {requisition.requisition_number}: "
                f"{action}"
            ),
            ip_address=request.remote_addr,
        )
        db.session.add(audit)
        db.session.commit()

        return redirect(url_for("requisition.detail", id=id))

    return render_template("requisition/review.html", requisition=requisition)


@requisition_bp.route("/approve/<int:id>", methods=["GET", "POST"])
@login_required
@active_user_required
@approver_required
def approve(id: int):
    requisition = Requisition.query.get_or_404(id)

    if requisition.status not in ["pending_approval", "partially_approved"]:
        flash("This requisition is not pending approval.", "warning")
        return redirect(url_for("requisition.detail", id=id))

    if not current_user.signature_path:
        flash(
            "You must upload your signature before approving. "
            "Please update your profile.",
            "warning",
        )
        return redirect(url_for("auth.profile"))

    existing_approval = ApprovalLog.query.filter_by(
        requisition_id=id,
        approver_id=current_user.id,
        action="approved",
    ).first()
    if existing_approval:
        flash("You have already approved this requisition.", "warning")
        return redirect(url_for("requisition.detail", id=id))

    current_approvals = ApprovalLog.query.filter_by(
        requisition_id=id, action="approved"
    ).count()
    next_level = current_approvals + 1

    if next_level == 3 and not current_user.is_senior_approver:
        flash("Only senior approvers can provide the third approval.", "warning")
        return redirect(url_for("requisition.detail", id=id))

    if request.method == "POST":
        action = request.form.get("action")
        comments = request.form.get("comments", "")

        approval_log = ApprovalLog(
            requisition_id=id,
            approver_id=current_user.id,
            approval_level=next_level,
            action=action,
            comments=comments,
            signature_path=current_user.signature_path,
        )
        db.session.add(approval_log)

        if action == "approved":
            requisition.current_approvals = next_level
            if next_level >= requisition.required_approvals:
                requisition.status = "approved"
                requisition.completed_at = datetime.utcnow()
                flash("Requisition has been fully approved!", "success")
            else:
                requisition.status = "partially_approved"
                flash(
                    f"Approval {next_level} of "
                    f"{requisition.required_approvals} completed.",
                    "success",
                )
        else:
            requisition.status = "rejected"
            flash("Requisition has been rejected.", "info")

        audit = AuditLog(
            user_id=current_user.id,
            action=f"approve_{action}",
            entity_type="requisition",
            entity_id=requisition.id,
            details=(
                f"Approval level {next_level} for requisition "
                f"{requisition.requisition_number}: {action}"
            ),
            ip_address=request.remote_addr,
        )
        db.session.add(audit)

        if requisition.status == "approved":
            notify(
                [requisition.initiator],
                f"{requisition.requisition_number} has been fully approved.",
                requisition,
                "approved",
            )
        elif requisition.status == "partially_approved":
            notify(
                [requisition.initiator],
                f"{requisition.requisition_number}: approval "
                f"{next_level} of {requisition.required_approvals} completed.",
                requisition,
                "update",
            )
            notify(
                active_users(can_approve=True),
                f"{requisition.requisition_number} is awaiting approval "
                f"{next_level + 1}.",
                requisition,
                "pending",
                exclude_id=current_user.id,
            )
        else:
            notify(
                [requisition.initiator],
                f"{requisition.requisition_number} was rejected at approval.",
                requisition,
                "rejected",
            )

        db.session.commit()
        return redirect(url_for("requisition.detail", id=id))

    return render_template(
        "requisition/approve.html",
        requisition=requisition,
        approval_level=next_level,
    )


# ---------------------------------------------------------------------------
# Download documents
# ---------------------------------------------------------------------------

@requisition_bp.route("/download/<int:id>/<format>")
@login_required
@active_user_required
def download(id: int, format: str):
    """Download requisition in the requested document format."""
    requisition = Requisition.query.get_or_404(id)
    generator = RequisitionDocumentGenerator(requisition)

    if format == "pdf":
        buffer = merge_with_documents(
            generator.generate_pdf(), requisition.documents
        )
        mimetype, ext = "application/pdf", "pdf"
    elif format == "docx":
        buffer = generator.generate_docx()
        mimetype = (
            "application/"
            "vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        ext = "docx"
    elif format == "xlsx":
        buffer = generator.generate_excel()
        mimetype = (
            "application/"
            "vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        ext = "xlsx"
    elif format == "csv":
        buffer = generator.generate_csv()
        mimetype, ext = "text/csv", "csv"
    else:
        flash("Invalid format requested.", "danger")
        return redirect(url_for("requisition.detail", id=id))

    return send_file(
        buffer,
        mimetype=mimetype,
        as_attachment=True,
        download_name=f"{requisition.requisition_number}.{ext}",
    )


@requisition_bp.route("/document/<int:id>")
@login_required
@active_user_required
def document(id: int):
    """Download a single supporting document."""
    import io

    from app.models import SupportingDocument

    doc = SupportingDocument.query.get_or_404(id)
    return send_file(
        io.BytesIO(doc.data),
        mimetype=doc.content_type,
        as_attachment=True,
        download_name=doc.filename,
    )


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def _report_filters():
    args = request.args
    initiator = (args.get("initiator") or "").strip()
    initiator_name = ""

    if initiator:
        try:
            user = User.query.get(int(initiator))
            initiator_name = user.full_name if user else ""
        except ValueError:
            initiator_name = ""

    return {
        "status": (args.get("status") or "").strip(),
        "currency": (args.get("currency") or "").strip(),
        "department": (args.get("department") or "").strip(),
        "initiator": initiator,
        "date_from": (args.get("date_from") or "").strip(),
        "date_to": (args.get("date_to") or "").strip(),
        "initiator_name": initiator_name,
    }


def _parse_date(value: str, fmt: str = "%Y-%m-%d"):
    try:
        return datetime.strptime(value, fmt)
    except (TypeError, ValueError):
        return None


def _report_query(filters):
    query = Requisition.query

    if (
        current_user.role != "superuser"
        and not (current_user.can_review or current_user.can_approve)
    ):
        query = query.filter(Requisition.initiator_id == current_user.id)

    status = filters.get("status")
    currency = filters.get("currency")
    initiator = filters.get("initiator")
    date_from_str = filters.get("date_from")
    date_to_str = filters.get("date_to")
    department = filters.get("department")

    if status:
        query = query.filter(Requisition.status == status)
    if currency:
        query = query.filter(Requisition.currency == currency)
    if initiator:
        try:
            initiator_id = int(initiator)
        except ValueError:
            initiator_id = None
        if initiator_id:
            query = query.filter(Requisition.initiator_id == initiator_id)

    if date_from_str:
        date_from = _parse_date(date_from_str)
        if date_from:
            query = query.filter(Requisition.created_at >= date_from)

    if date_to_str:
        date_to = _parse_date(date_to_str)
        if date_to:
            query = query.filter(
                Requisition.created_at < date_to + timedelta(days=1)
            )

    if department:
        query = query.join(RequisitionItem).filter(
            RequisitionItem.account_department == department
        ).distinct()

    return query.order_by(Requisition.created_at.desc()).all()


@requisition_bp.route("/reports")
@login_required
@active_user_required
def reports():
    filters = _report_filters()
    results = _report_query(filters)

    statuses = [
        "draft",
        "pending_review",
        "pending_approval",
        "partially_approved",
        "approved",
        "rejected",
    ]
    currencies = ["USD", "ZWG", "ZAR", "BWP"]
    departments = ["EB", "FIN"]

    users = (
        User.query.filter_by(is_active=True)
        .order_by(User.first_name)
        .all()
    )

    from app.utils.reports import totals_by_currency

    summary = {
        "count": len(results),
        "totals": totals_by_currency(results),
        "approved": sum(1 for r in results if r.status == "approved"),
        "pending": sum(
            1
            for r in results
            if r.status
            in ("pending_review", "pending_approval", "partially_approved")
        ),
    }

    return render_template(
        "requisition/reports.html",
        filters=filters,
        results=results,
        statuses=statuses,
        currencies=currencies,
        departments=departments,
        users=users,
        summary=summary,
    )


@requisition_bp.route("/reports/export/<fmt>")
@login_required
@active_user_required
def reports_export(fmt: str):
    if fmt not in ("csv", "xlsx", "pdf"):
        flash("Unsupported export format.", "warning")
        return redirect(url_for("requisition.reports"))

    filters = _report_filters()
    results = _report_query(filters)

    from app.utils.reports import to_csv, to_excel, describe_filters
    from app.utils.pdf_export import to_pdf

    meta = {
        "generated": datetime.utcnow().strftime("%d %b %Y %H:%M UTC"),
        "filters": describe_filters(filters),
    }

    if fmt == "csv":
        buf = to_csv(results, meta)
        mimetype, ext = "text/csv", "csv"
    elif fmt == "xlsx":
        buf = to_excel(results, meta)
        mimetype = (
            "application/"
            "vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        ext = "xlsx"
    else:
        buf = to_pdf(results, meta)
        mimetype, ext = "application/pdf", "pdf"

    db.session.add(
        AuditLog(
            user_id=current_user.id,
            action="export_report",
            entity_type="report",
            entity_id=0,
            details=f"Exported {fmt} report ({len(results)} rows)",
            ip_address=request.remote_addr,
        )
    )
    db.session.commit()

    return send_file(
        buf,
        mimetype=mimetype,
        as_attachment=True,
        download_name=(
            f"requisition_report_"
            f"{datetime.utcnow().strftime('%Y%m%d_%H%M')}.{ext}"
        ),
    )


# ---------------------------------------------------------------------------
# Convenience queues
# ---------------------------------------------------------------------------

@requisition_bp.route("/pending-review")
@login_required
@active_user_required
@reviewer_required
def pending_review():
    page = request.args.get("page", 1, type=int)
    requisitions = (
        Requisition.query.filter_by(status="pending_review")
        .order_by(Requisition.created_at.desc())
        .paginate(page=page, per_page=20)
    )

    return render_template(
        "requisition/list.html",
        requisitions=requisitions,
        title="Pending Review",
        status_filter="pending_review",
    )


@requisition_bp.route("/review-queue")
@login_required
@active_user_required
@reviewer_required
def review_queue():
    page = request.args.get("page", 1, type=int)
    tab = (request.args.get("tab") or "pending").strip()

    tab_statuses = {
        "pending": ["pending_review"],
        "awaiting_approval": ["pending_approval", "partially_approved"],
        "completed": ["approved", "rejected"],
    }
    if tab not in tab_statuses:
        tab = "pending"

    base_query = (
        Requisition.query.filter(Requisition.reviewer_id == current_user.id)
        if tab == "completed"
        else Requisition.query
    )
    query = base_query.filter(Requisition.status.in_(tab_statuses[tab]))
    requisitions = query.order_by(Requisition.created_at.desc()).paginate(
        page=page, per_page=20
    )

    tabs_config = [
        ("pending", "Pending Review"),
        ("awaiting_approval", "Awaiting Approval"),
        ("completed", "Completed"),
    ]
    tabs = [
        (
            key,
            label,
            Requisition.query.filter(
                Requisition.status.in_(tab_statuses[key])
            ).count(),
        )
        for key, label in tabs_config
    ]
    counts = {key: count for key, _label, count in tabs}
    total_value = sum((r.total_debit or 0) for r in requisitions.items)

    return render_template(
        "requisition/review_queue.html",
        requisitions=requisitions,
        title="Review Queue",
        status_filter=tab,
        tabs=tabs,
        queue_tab=tab,
        counts=counts,
        total_value=total_value,
    )


@requisition_bp.route("/pending-approval")
@login_required
@active_user_required
@approver_required
def pending_approval():
    page = request.args.get("page", 1, type=int)
    requisitions = (
        Requisition.query.filter(
            Requisition.status.in_(
                ["pending_approval", "partially_approved"]
            )
        )
        .order_by(Requisition.created_at.desc())
        .paginate(page=page, per_page=20)
    )

    return render_template(
        "requisition/list.html",
        requisitions=requisitions,
        title="Pending Approval",
        status_filter="pending_approval",
    )


@requisition_bp.route("/my-requisitions")
@login_required
@active_user_required
def my_requisitions():
    page = request.args.get("page", 1, type=int)
    requisitions = (
        Requisition.query.filter_by(initiator_id=current_user.id)
        .order_by(Requisition.created_at.desc())
        .paginate(page=page, per_page=20)
    )

    return render_template(
        "requisition/list.html",
        requisitions=requisitions,
        title="My Requisitions",
    )


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@requisition_bp.route("/search")
@login_required
@active_user_required
def search():
    from sqlalchemy import or_

    q = (request.args.get("q") or "").strip()
    results = []

    if q:
        query = Requisition.query
        if (
            current_user.role != "superuser"
            and not (current_user.can_review or current_user.can_approve)
        ):
            query = query.filter(Requisition.initiator_id == current_user.id)

        like = f"%{q}%"
        results = (
            query.filter(
                or_(
                    Requisition.requisition_number.ilike(like),
                    Requisition.in_favor_of.ilike(like),
                    Requisition.bank_name.ilike(like),
                    Requisition.account_number.ilike(like),
                    Requisition.reason_for_payment.ilike(like),
                    Requisition.status.ilike(like),
                    Requisition.currency.ilike(like),
                )
            )
            .order_by(Requisition.created_at.desc())
            .limit(100)
            .all()
        )

    return render_template("requisition/search.html", q=q, results=results)


# ---------------------------------------------------------------------------
# Batching utilities
# ---------------------------------------------------------------------------

def _can_batch() -> bool:
    return (
        current_user.role == "superuser"
        or current_user.can_review
        or current_user.can_approve
    )


def _pending_batch_query():
    """Approved requisitions that have not yet been downloaded in a batch."""
    from app.models import BatchItem

    batched = db.session.query(BatchItem.requisition_id)
    return Requisition.query.filter(
        Requisition.status == "approved", ~Requisition.id.in_(batched)
    )


def _next_batch_number() -> str:
    from app.models import RequisitionBatch

    prefix = f"BATCH-{datetime.utcnow():%Y%m%d}"
    count = RequisitionBatch.query.filter(
        RequisitionBatch.batch_number.like(prefix + "%")
    ).count()
    return f"{prefix}-{count + 1:03d}"


def _batch_response(batch, rows, fmt: str):
    """Send batch file back to client.

    rows: list of (requisition, reference, account_name, code)
    """
    from app.utils.batch import to_batch_csv, to_batch_excel

    if fmt == "csv":
        buf = to_batch_csv(rows)
        mimetype, ext = "text/csv", "csv"
    else:
        buf = to_batch_excel(rows)
        mimetype = (
            "application/"
            "vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        ext = "xlsx"

    return send_file(
        buf,
        mimetype=mimetype,
        as_attachment=True,
        download_name=f"{batch.batch_number}.{ext}",
    )


@requisition_bp.route("/batches")
@login_required
@active_user_required
def batches():
    from app.models import RequisitionBatch, BatchItem
    from app.utils.batch import (
        payment_code,
        default_reference,
        default_account_name,
        net_amount,
    )

    if not _can_batch():
        flash("You do not have access to batching.", "warning")
        return redirect(url_for("requisition.dashboard"))

    pending = [
        (r, payment_code(r), default_reference(r), default_account_name(r))
        for r in _pending_batch_query()
        .order_by(Requisition.currency, Requisition.created_at)
        .all()
    ]

    history = []
    for batch in (
        RequisitionBatch.query.order_by(
            RequisitionBatch.created_at.desc()
        ).all()
    ):
        rows = [
            (
                bi.requisition,
                bi.code or payment_code(bi.requisition),
                bi.reference or bi.requisition.requisition_number,
                bi.account_name or bi.requisition.in_favor_of,
            )
            for bi in batch.items
        ]
        history.append((batch, rows))

    return render_template(
        "requisition/batches.html",
        pending=pending,
        history=history,
        batched_count=BatchItem.query.count(),
        net_amount=net_amount,
    )


@requisition_bp.route("/batches/create", methods=["POST"])
@login_required
@active_user_required
def batch_create():
    from decimal import Decimal

    from sqlalchemy.exc import IntegrityError

    from app.models import RequisitionBatch, BatchItem
    from app.utils.batch import (
        net_amount,
        clean_text,
        default_reference,
        default_account_name,
        payment_code,
    )

    if not _can_batch():
        flash("You do not have access to batching.", "warning")
        return redirect(url_for("requisition.dashboard"))

    fmt = request.form.get("format")
    ids = request.form.getlist("ids", type=int)

    if fmt not in ("csv", "xlsx") or not ids:
        flash(
            "Select at least one approved payment and a file format.",
            "warning",
        )
        return redirect(url_for("requisition.batches"))

    requisitions = (
        _pending_batch_query()
        .filter(Requisition.id.in_(ids))
        .order_by(Requisition.created_at)
        .all()
    )
    if not requisitions:
        flash(
            "The selected payments are already batched or not approved.",
            "warning",
        )
        return redirect(url_for("requisition.batches"))

    if len({r.currency for r in requisitions}) > 1:
        flash("A batch can only contain one currency.", "warning")
        return redirect(url_for("requisition.batches"))

    rows = []
    for r in requisitions:
        reference = default_reference(r)
        account_name = default_account_name(r)
        code = clean_text(
            request.form.get(f"code_{r.id}"),
            payment_code(r),
            50,
        )
        rows.append((r, reference, account_name, code))

    total = sum((net_amount(r) for r in requisitions), Decimal("0.00"))

    batch = RequisitionBatch(
        batch_number=_next_batch_number(),
        currency=requisitions[0].currency,
        row_count=len(requisitions),
        total_amount=float(total),
        created_by_id=current_user.id,
    )
    db.session.add(batch)
    db.session.flush()

    for r, reference, account_name, code in rows:
        db.session.add(
            BatchItem(
                batch_id=batch.id,
                requisition_id=r.id,
                reference=reference,
                account_name=account_name,
                code=code,
            )
        )

    db.session.add(
        AuditLog(
            user_id=current_user.id,
            action="create_batch",
            entity_type="batch",
            entity_id=batch.id,
            details=(
                f"Batch {batch.batch_number}: "
                f"{len(requisitions)} payment(s), "
                f"{batch.currency} {total}"
            ),
            ip_address=request.remote_addr,
        )
    )

    try:
        for r in requisitions:
            notify(
                [r.initiator],
                f"{r.requisition_number} was batched in {batch.batch_number}.",
                r,
                "batched",
            )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash(
            "One or more payments were batched by someone else. "
            "Please try again.",
            "warning",
        )
        return redirect(url_for("requisition.batches"))

    flash(
        f"{batch.batch_number} created with {len(requisitions)} payment(s).",
        "success",
    )
    return _batch_response(batch, rows, fmt)


@requisition_bp.route("/batches/<int:id>/download/<fmt>")
@login_required
@active_user_required
def batch_download(id: int, fmt: str):
    from app.models import RequisitionBatch, BatchItem
    from app.utils.batch import payment_code

    if not _can_batch() or fmt not in ("csv", "xlsx"):
        flash("Batch download is not available.", "warning")
        return redirect(url_for("requisition.batches"))

    batch = RequisitionBatch.query.get_or_404(id)
    items = (
        BatchItem.query.filter_by(batch_id=id)
        .order_by(BatchItem.id)
        .all()
    )

    rows = [
        (
            bi.requisition,
            bi.reference or bi.requisition.requisition_number,
            bi.account_name or bi.requisition.in_favor_of,
            bi.code or payment_code(bi.requisition),
        )
        for bi in items
    ]

    return _batch_response(batch, rows, fmt)
