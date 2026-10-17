import os
from werkzeug.utils import secure_filename
from flask import current_app
from PIL import Image
import uuid

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_signature(file, user_id):
    """Save uploaded signature file"""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower()
        unique_filename = f"signature_{user_id}_{uuid.uuid4().hex[:8]}.{ext}"

        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)

        # Process image - resize if needed
        img = Image.open(file)
        img.thumbnail((300, 150), Image.Resampling.LANCZOS)

        # Convert to RGB if necessary (for PNG with transparency)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background

        img.save(filepath, quality=95)

        return unique_filename
    return None

def format_currency(amount, currency='USD'):
    """Format amount with currency symbol"""
    symbols = {
        'USD': '$',
        'ZWG': 'ZWG$',
        'ZAR': 'R',
        'BWP': 'P'
    }
    symbol = symbols.get(currency, currency)
    return f"{symbol}{amount:,.2f}"

def get_status_badge_class(status):
    """Return Bootstrap badge class for status"""
    classes = {
        'draft': 'bg-secondary',
        'pending_review': 'bg-info',
        'pending_approval': 'bg-warning',
        'partially_approved': 'bg-primary',
        'approved': 'bg-success',
        'rejected': 'bg-danger'
    }
    return classes.get(status, 'bg-secondary')

def get_status_display(status):
    """Return human-readable status"""
    displays = {
        'draft': 'Draft',
        'pending_review': 'Pending Review',
        'pending_approval': 'Pending Approval',
        'partially_approved': 'Partially Approved',
        'approved': 'Approved',
        'rejected': 'Rejected'
    }
    return displays.get(status, status.title())
