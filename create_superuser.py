from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash
import getpass

def create_superuser():
    app = create_app()
    with app.app_context():
        db.create_all()
        
        print("=== Create Superuser for First Mutual Life Requisition System ===")
        
        email = input("Enter email: ")
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            print("User with this email already exists!")
            return
        
        first_name = input("Enter first name: ")
        last_name = input("Enter last name: ")
        employee_id = input("Enter employee ID: ")
        department = input("Enter department: ")
        password = getpass.getpass("Enter password: ")
        confirm_password = getpass.getpass("Confirm password: ")
        
        if password != confirm_password:
            print("Passwords do not match!")
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
            is_senior_approver=True
        )
        
        db.session.add(superuser)
        db.session.commit()
        
        print(f"Superuser '{email}' created successfully!")

if __name__ == '__main__':
    create_superuser()
