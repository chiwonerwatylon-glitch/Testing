import base64
import hashlib
import hmac
import io
import os

import qrcode
from flask import current_app, url_for


def signing_key():
    return os.environ.get('REQUISITION_SIGNING_KEY') or current_app.config['SECRET_KEY']


def requisition_payload(req):
    logs = sorted(
        f"{log.approver_id}:{log.approval_level}:{log.action}" for log in req.approval_logs
    )
    parts = [
        req.requisition_number,
        req.currency or '',
        f"{(req.total_debit or 0):.2f}",
        f"{(req.total_credit or 0):.2f}",
        req.status or '',
        str(req.required_approvals or 0),
        str(req.items.count()),
        ';'.join(logs),
    ]
    return '|'.join(parts)


def requisition_signature(req):
    digest = hmac.new(signing_key().encode(), requisition_payload(req).encode(), hashlib.sha256)
    return digest.hexdigest()[:32]


def file_sha256(filename):
    if not filename:
        return None
    path = os.path.join(current_app.root_path, 'static', 'signatures', filename)
    if not os.path.exists(path):
        return None
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def verification_url(req):
    return url_for('requisition.verify', id=req.id, s=requisition_signature(req), _external=True)


def qr_data_uri(text):
    img = qrcode.make(text, box_size=4, border=1)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
