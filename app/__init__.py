from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
import os

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fml-requisition-secret-key-2024')
    if not os.environ.get('SECRET_KEY') and not os.environ.get('REQUISITION_SIGNING_KEY'):
        app.logger.warning('SECRET_KEY is not set; requisition security codes use a default key.')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///fml_requisition.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'signatures')
    
    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    
    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.requisition import requisition_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(requisition_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    
    # Ensure database tables exist (gunicorn does not run run.py's __main__ block)
    with app.app_context():
        db.create_all()
        seed_superuser(app)
    
    return app

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))

def seed_superuser(app):
    """Create a superuser from environment variables if it does not exist yet.

    Reads ADMIN_EMAIL and ADMIN_PASSWORD. Optional: ADMIN_FIRST_NAME (default 'Admin'),
    ADMIN_LAST_NAME (default 'User'), ADMIN_EMPLOYEE_ID (default 'ADMIN001'),
    ADMIN_DEPARTMENT (default 'IT'). Never hardcode credentials in this file.
    """
    email = os.environ.get('ADMIN_EMAIL')
    password = os.environ.get('ADMIN_PASSWORD')
    if not email or not password:
        return

    from app.models import User
    from werkzeug.security import generate_password_hash

    first_name = os.environ.get('ADMIN_FIRST_NAME') or 'Admin'
    last_name = os.environ.get('ADMIN_LAST_NAME') or 'User'
    employee_id = os.environ.get('ADMIN_EMPLOYEE_ID') or 'ADMIN001'
    department = os.environ.get('ADMIN_DEPARTMENT') or 'IT'

    with app.app_context():
        user = User.query.filter_by(email=email).first()

        if user:
            # Never overwrite an existing password; only ensure admin privileges.
            changed = False
            for attr, value in (
                ('role', 'superuser'),
                ('is_active', True),
                ('can_initiate', True),
                ('can_review', True),
                ('can_approve', True),
                ('is_senior_approver', True),
            ):
                if getattr(user, attr) != value:
                    setattr(user, attr, value)
                    changed = True
            if changed:
                db.session.commit()
                app.logger.info('Updated existing user to superuser privileges: %s', email)
            return

        if User.query.filter_by(employee_id=employee_id).first():
            app.logger.warning(
                'Skipping superuser creation: employee_id %s is already used by another user.',
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
            role='superuser',
            is_active=True,
            can_initiate=True,
            can_review=True,
            can_approve=True,
            is_senior_approver=True,
        )
        db.session.add(superuser)
        db.session.commit()
        app.logger.info('Created superuser: %s', email)
