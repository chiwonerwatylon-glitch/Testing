"""
First Mutual Life Assurance Company - Requisition System
Utils Package

This package contains helper utilities used across the application:

- decorators: Role-based access control decorators
- helpers: General helper functions (file handling, formatting, etc.)
- document_generator: PDF/DOCX/Excel/CSV requisition document generation
"""

from __future__ import annotations

from app.utils.decorators import (
    active_user_required,
    approver_required,
    initiator_required,
    reviewer_required,
    superuser_required,
)
from app.utils.document_generator import RequisitionDocumentGenerator
from app.utils.helpers import (
    allowed_file,
    format_currency,
    get_status_badge_class,
    get_status_display,
    save_signature,
)

__all__ = [
    # Decorators
    "superuser_required",
    "reviewer_required",
    "approver_required",
    "initiator_required",
    "active_user_required",

    # Helpers
    "allowed_file",
    "save_signature",
    "format_currency",
    "get_status_badge_class",
    "get_status_display",

    # Document Generator
    "RequisitionDocumentGenerator",
]
