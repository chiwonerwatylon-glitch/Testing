from __future__ import annotations

import os
import uuid
from typing import Optional

from flask import current_app
from PIL import Image
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def allowed_file(filename: str) -> bool:
    """Return True if the filename has an allowed image extension."""
    return (
        bool(filename)
        and "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def save_signature(file, user_id: str | int) -> Optional[str]:
    """Save an uploaded signature image for the given user and return the filename.

    The image is:
    - renamed to include the user_id and a short UUID
    - resized (thumbnail) to max 300x150
    - converted to RGB with white background if it has transparency
    """
    if not file or not allowed_file(file.filename):
        return None

    filename = secure_filename(file.filename)
    if "." not in filename:
        return None

    ext = filename.rsplit(".", 1)[1].lower()
    unique_filename = f"signature_{user_id}_{uuid.uuid4().hex[:8]}.{ext}"
    upload_folder = current_app.config.get("UPLOAD_FOLDER")

    if not upload_folder:
        # Misconfiguration guard: do not attempt to save without a folder
        current_app.logger.error("UPLOAD_FOLDER is not configured.")
        return None

    filepath = os.path.join(upload_folder, unique_filename)

    try:
        img = Image.open(file)
        img.thumbnail((300, 150), Image.Resampling.LANCZOS)

        # Convert to RGB if necessary (for PNG with transparency or palette images)
        if img.mode in ("RGBA", "LA", "P"):
            if img.mode == "P":
                img = img.convert("RGBA")
            background = Image.new("RGB", img.size, (255, 255, 255))
            # Use alpha channel as mask if present
            alpha = img.split()[-1] if img.mode == "RGBA" else None
            background.paste(img, mask=alpha)
            img = background

        img.save(filepath, quality=95)
    except Exception as exc:  # best-effort; log and fail gracefully
        current_app.logger.exception("Failed to save signature image: %s", exc)
        return None

    return unique_filename


def format_currency(amount: float | int, currency: str = "USD") -> str:
    """Format amount with currency symbol and 2 decimal places."""
    symbols = {
        "USD": "$",
        "ZWG": "ZWG$",
        "ZAR": "R",
        "BWP": "P",
    }
    symbol = symbols.get(currency, currency)
    try:
        value = float(amount)
    except (TypeError, ValueError):
        value = 0.0
    return f"{symbol}{value:,.2f}"


def get_status_badge_class(status: str) -> str:
    """Return Bootstrap badge class for a given requisition status."""
    classes = {
        "draft": "bg-secondary",
        "pending_review": "bg-info",
        "pending_approval": "bg-warning",
        "partially_approved": "bg-primary",
        "approved": "bg-success",
        "rejected": "bg-danger",
    }
    return classes.get(status, "bg-secondary")


def get_status_display(status: str) -> str:
    """Return human-readable label for a requisition status."""
    displays = {
        "draft": "Draft",
        "pending_review": "Pending Review",
        "pending_approval": "Pending Approval",
        "partially_approved": "Partially Approved",
        "approved": "Approved",
        "rejected": "Rejected",
        "recalled": "Recalled",
    }
    return displays.get(status, status.title() if isinstance(status, str) else str(status))
