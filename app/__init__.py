from __future__ import annotations

import logging
import os
from datetime import datetime

from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.exc import IntegrityError

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()


def create_app() -> Flask:
    """Application factory for the FML Requisition System."""
    app = Flask(__name__)

    # Configuration
    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY", "fml-requisition-secret-key-2024"
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///fml_requisition.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max file size
    app.config["UPLOAD_FOLDER"] = os.path.join(
        app.root_path, "static", "signatures"
    )

    # Ensure upload folder exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"

    # Register blueprints
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    from app.routes.assistant import assistant_bp
    from app.routes.auth import auth_bp
    from app.routes.requisition import requisition_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(requisition_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(assistant_bp)

    # Ensure database tables and batch columns exist; seed superuser
    with app.app_context():
        db.create_all()
        _ensure_batch_columns()
        seed_superuser(app)

        # Wire up the Gemini assistant: live system data and daily KB refresh
        from app.utils.gemini import (
            register_system_data_provider,
            start_background_refresh,
        )

        register_system_data_provider(_system_snapshot)
        start_background_refresh()

    return app


def _system_snapshot() -> str:
    """Return a privacy-conscious summary of requisition counts.

    Contains counts only (no names, account numbers, bank details or payment
    reasons). Returns an empty string on failure so the assistant never breaks.
    """
    try:
        from app.models import Requisition

        first_of_month = datetime.utcnow().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

        total = Requisition.query.count()
        draft = Requisition.query.filter_by(status="draft").count()
        pending_review = Requisition.query.filter_by(
            status="pending_review"
        ).count()
        pending_approval = (
            Requisition.query.filter_by(status="pending_approval").count()
            + Requisition.query.filter_by(status="partially_approved").count()
        )
        approved_this_month = Requisition.query.filter(
            Requisition.status == "approved",
            Requisition.completed_at >= first_of_month,
        ).count()
        rejected = Requisition.query.filter_by(status="rejected").count()

        return (
            f"Total requisitions: {total}\n"
            f"Draft: {draft}\n"
            f"Pending review: {pending_review}\n"
            f"Pending approval: {pending_approval}\n"
            f"Approved this month: {approved_this_month}\n"
            f"Rejected: {rejected}\n"
        )
    except Exception:
        logging.getLogger(__name__).exception(
            "Failed to build system snapshot for assistant"
        )
        return ""


@login_manager.user_loader
def load_user(user_id: str):
    """Flask-Login user loader callback."""
    from app.models import User

    try:
        return User.query.get(int(user_id))
    except (TypeError, ValueError):
        return None


def seed_superuser(app: Flask) -> None:
    """Create or update a superuser based on environment variables.

    Reads:
        ADMIN_EMAIL, ADMIN_PASSWORD
        Optional:
            ADMIN_FIRST_NAME (default 'Admin'),
            ADMIN_LAST_NAME (default 'User'),
            ADMIN_EMPLOYEE_ID (default 'ADMIN001'),
            ADMIN_DEPARTMENT (default 'IT').

    Never hardcode credentials in this file.
    """
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    if not email or not password:
        return

    from app.models import User
    from werkzeug.security import generate_password_hash

    first_name = os.environ.get("ADMIN_FIRST_NAME") or "Admin"
    last_name = os.environ.get("ADMIN_LAST_NAME") or "User"
    employee_id = os.environ.get("ADMIN_EMPLOYEE_ID") or "ADMIN001"
    department = os.environ.get("ADMIN_DEPARTMENT") or "IT"

    with app.app_context():
        user = User.query.filter_by(email=email).first()

        if user:
            # Never overwrite an existing password; only ensure admin privileges.
            changed = False
            for attr, value in (
                ("role", "superuser"),
                ("is_active", True),
                ("can_initiate", True),
                ("can_review", True),
                ("can_approve", True),
                ("is_senior_approver", True),
            ):
                if getattr(user, attr) != value:
                    setattr(user, attr, value)
                    changed = True
            if changed:
                db.session.commit()
                app.logger.info(
                    "Updated existing user to superuser privileges: %s",
                    email,
                )
            return

        if User.query.filter_by(employee_id=employee_id).first():
            app.logger.warning(
                "Skipping superuser creation: employee_id %s is already used by "
                "another user.",
                employee_id,
            )
            return

        superuser = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            employee_id=employee_id,
            department=department,
            password_hash=generate_password_hash(password),
            role="superuser",
            is_active=True,
            can_initiate=True,
            can_review=True,
            can_approve=True,
            is_senior_approver=True,
        )
        db.session.add(superuser)
        try:
            db.session.commit()
        except IntegrityError:
            # Another gunicorn worker created the same admin at boot. Not an error.
            db.session.rollback()
            app.logger.info(
                "Superuser %s already created by another worker.", email
            )
            return
        app.logger.info("Created superuser: %s", email)


def _ensure_batch_columns() -> None:
    """Add missing batch_items columns for older databases.

    create_all() does not add columns to existing tables, so we patch them here.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    if "batch_items" not in inspector.get_table_names():
        return

    columns = {c["name"] for c in inspector.get_columns("batch_items")}
    wanted = {
        "reference": "VARCHAR(255)",
        "account_name": "VARCHAR(200)",
        "code": "VARCHAR(50)",
    }

    with db.engine.begin() as conn:
        for name, ddl in wanted.items():
            if name not in columns:
                conn.execute(
                    text(f"ALTER TABLE batch_items ADD COLUMN {name} {ddl}")
                )
