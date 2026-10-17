import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'fml-requisition-secret-key-2024'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///fml_requisition.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    
    # FML Specific Config
    COMPANY_NAME = "First Mutual Life Assurance Company"
    COMPANY_SHORT_NAME = "FML"
    LOW_AMOUNT_THRESHOLD = 5000  # USD
    MIN_APPROVERS_LOW = 2
    MIN_APPROVERS_HIGH = 3
    
    # Allowed signature file extensions
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
