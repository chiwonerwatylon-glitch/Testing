from __future__ import annotations

from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(
        db.String(120), unique=True, nullable=False, index=True
    )
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    employee_id = db.Column(db.String(20), unique=True, nullable=False)
    department = db.Column(db.String(100), nullable=False)
    position = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    signature_path = db.Column(db.String(255))

    # Role and permissions
    role = db.Column(db.String(20), default="user")  # user, reviewer, approver, superuser
    is_active = db.Column(db.Boolean, default=False)
    can_initiate = db.Column(db.Boolean, default=False)
    can_review = db.Column(db.Boolean, default=False)
    can_approve = db.Column(db.Boolean, default=False)
    is_senior_approver = db.Column(db.Boolean, default=False)  # 3rd approver

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    initiated_requisitions = db.relationship(
        "Requisition",
        backref="initiator",
        foreign_keys="Requisition.initiator_id",
        lazy="dynamic",
    )
    reviewed_requisitions = db.relationship(
        "Requisition",
        backref="reviewer",
        foreign_keys="Requisition.reviewer_id",
        lazy="dynamic",
    )
    approval_logs = db.relationship(
        "ApprovalLog", backref="approver", lazy="dynamic"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class Requisition(db.Model):
    __tablename__ = "requisitions"

    id = db.Column(db.Integer, primary_key=True)
    requisition_number = db.Column(
        db.String(50), unique=True, nullable=False, index=True
    )

    # Payment details
    in_favor_of = db.Column(db.String(200), nullable=False)
    bank_name = db.Column(db.String(100), nullable=False)
    branch = db.Column(db.String(100), nullable=False)
    account_number = db.Column(db.String(50), nullable=False)

    # Payment reason
    reason_for_payment = db.Column(db.Text, nullable=False)
    itf_263 = db.Column(db.String(10), default="NA")  # Yes, No, NA

    # Amount info
    currency = db.Column(db.String(10), default="USD")
    total_debit = db.Column(db.Float, default=0.0)
    total_credit = db.Column(db.Float, default=0.0)

    # Status tracking
    # draft, pending_review, pending_approval, partially_approved, approved, rejected
    status = db.Column(db.String(30), default="draft")

    # Workflow tracking
    initiator_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    initiated_at = db.Column(db.DateTime)
    initiator_signature = db.Column(db.String(255))

    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    reviewed_at = db.Column(db.DateTime)
    reviewer_signature = db.Column(db.String(255))
    review_comments = db.Column(db.Text)

    # Rejection / resubmission
    rejection_reason = db.Column(db.Text)
    rejected_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    rejected_at = db.Column(db.DateTime)
    resubmit_count = db.Column(db.Integer, default=0)

    required_approvals = db.Column(db.Integer, default=2)
    current_approvals = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    completed_at = db.Column(db.DateTime)

    # Relationships
    rejected_by = db.relationship("User", foreign_keys=[rejected_by_id])
    items = db.relationship(
        "RequisitionItem",
        backref="requisition",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    approval_logs = db.relationship(
        "ApprovalLog",
        backref="requisition",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def calculate_required_approvals(self) -> int:
        """Calculate required approvals based on amount and currency."""
        if self.currency == "USD" and (self.total_debit or 0) >= 5000:
            return 3
        return 2

    def get_approval_status(self) -> dict:
        """Get detailed approval status."""
        approvals = ApprovalLog.query.filter_by(
            requisition_id=self.id, action="approved"
        ).all()

        return {
            "required": self.required_approvals,
            "completed": len(approvals),
            "approvers": [a.approver.full_name for a in approvals],
            "pending": max(self.required_approvals - len(approvals), 0),
        }

    @staticmethod
    def generate_requisition_number() -> str:
        """Generate unique requisition number of the form FML-REQ-YYYYMMDD-0001."""
        today = datetime.utcnow()
        prefix = f"FML-REQ-{today.strftime('%Y%m%d')}"

        last_req = (
            Requisition.query.filter(
                Requisition.requisition_number.like(f"{prefix}%")
            )
            .order_by(Requisition.id.desc())
            .first()
        )

        if last_req:
            try:
                last_num = int(last_req.requisition_number.split("-")[-1])
            except (ValueError, AttributeError):
                last_num = 0
            new_num = last_num + 1
        else:
            new_num = 1

        return f"{prefix}-{new_num:04d}"

    def __repr__(self) -> str:
        return f"<Requisition {self.requisition_number}>"


class RequisitionItem(db.Model):
    __tablename__ = "requisition_items"

    id = db.Column(db.Integer, primary_key=True)
    requisition_id = db.Column(
        db.Integer, db.ForeignKey("requisitions.id"), nullable=False
    )

    account_name = db.Column(db.String(100), nullable=False)
    account_code = db.Column(db.String(50), nullable=False)
    account_location = db.Column(db.String(100))
    account_department = db.Column(db.String(100))
    details = db.Column(db.Text)
    debit = db.Column(db.Float, default=0.0)
    credit = db.Column(db.Float, default=0.0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<RequisitionItem {self.account_name}>"


class SupportingDocument(db.Model):
    """Supporting document (PDF or image) stored in the database."""

    __tablename__ = "supporting_documents"

    id = db.Column(db.Integer, primary_key=True)
    requisition_id = db.Column(
        db.Integer, db.ForeignKey("requisitions.id"), nullable=False, index=True
    )
    filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(100), nullable=False)
    data = db.Column(db.LargeBinary, nullable=False)
    size = db.Column(db.Integer, default=0)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    requisition = db.relationship(
        "Requisition",
        backref=db.backref(
            "documents",
            lazy=True,
            order_by="SupportingDocument.id",
            cascade="all, delete-orphan",
        ),
    )


class ApprovalLog(db.Model):
    __tablename__ = "approval_logs"

    id = db.Column(db.Integer, primary_key=True)
    requisition_id = db.Column(
        db.Integer, db.ForeignKey("requisitions.id"), nullable=False
    )
    approver_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )

    approval_level = db.Column(db.Integer, nullable=False)  # 1, 2, or 3
    action = db.Column(db.String(20), nullable=False)  # approved, rejected
    comments = db.Column(db.Text)
    signature_path = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ApprovalLog {self.requisition_id} - Level {self.approval_level}>"


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.user_id}>"


class RequisitionBatch(db.Model):
    """A Stanbic upload batch. Created when a batch file is downloaded."""

    __tablename__ = "requisition_batches"

    id = db.Column(db.Integer, primary_key=True)
    batch_number = db.Column(
        db.String(40), unique=True, nullable=False, index=True
    )
    currency = db.Column(db.String(10), nullable=False)
    row_count = db.Column(db.Integer, default=0)
    total_amount = db.Column(db.Float, default=0.0)
    created_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    created_by = db.relationship("User", backref="batches")

    def __repr__(self) -> str:
        return f"<RequisitionBatch {self.batch_number}>"


class BatchItem(db.Model):
    """Links an approved requisition to the batch it was downloaded in.

    One batch per requisition.
    """

    __tablename__ = "batch_items"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(
        db.Integer,
        db.ForeignKey("requisition_batches.id"),
        nullable=False,
        index=True,
    )
    requisition_id = db.Column(
        db.Integer,
        db.ForeignKey("requisitions.id"),
        nullable=False,
        unique=True,
    )
    reference = db.Column(
        db.String(255)
    )  # editable at batching; defaults to reason for payment
    account_name = db.Column(
        db.String(200)
    )  # editable at batching; defaults to In Favor Of
    code = db.Column(
        db.String(50)
    )  # editable at batching; defaults to the first line item's account code
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    batch = db.relationship(
        "RequisitionBatch",
        backref=db.backref("items", order_by="BatchItem.id"),
    )
    requisition = db.relationship(
        "Requisition",
        backref=db.backref("batch_item", uselist=False),
    )

    def __repr__(self) -> str:
        return f"<BatchItem {self.requisition_id} in {self.batch_id}>"


class Notification(db.Model):
    """In-app notice about a requisition change, shown in the navbar bell."""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    requisition_id = db.Column(
        db.Integer, db.ForeignKey("requisitions.id"), nullable=True
    )
    message = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(20), default="info")
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship(
        "User", backref=db.backref("notifications", lazy="dynamic")
    )
    requisition = db.relationship("Requisition")

    def __repr__(self) -> str:
        return f"<Notification {self.user_id}: {self.message[:30]}>"
