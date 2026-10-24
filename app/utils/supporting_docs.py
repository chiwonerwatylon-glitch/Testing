from __future__ import annotations

import io
import os

from flask_login import current_user
from PIL import Image
from pypdf import PdfReader, PdfWriter
from werkzeug.utils import secure_filename

from app.models import SupportingDocument

IMAGE_TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}
ALLOWED = {"pdf": "application/pdf", **IMAGE_TYPES}


def save_supporting_documents(requisition, files) -> int:
    """Validate and store uploaded files on the requisition. Raises ValueError."""
    count = 0
    for f in files:
        if not f or not f.filename:
            continue
        name = secure_filename(f.filename) or "document"
        ext = os.path.splitext(name)[1].lstrip(".").lower()
        if ext not in ALLOWED:
            raise ValueError(f"'{f.filename}': only PDF, PNG and JPG files are allowed.")
        data = f.read()
        if not data:
            continue
        try:
            if ext == "pdf":
                PdfReader(io.BytesIO(data))
            else:
                Image.open(io.BytesIO(data)).verify()
        except Exception:
            raise ValueError(f"'{f.filename}' is not a valid {ext.upper()} file.")
        requisition.documents.append(
            SupportingDocument(
                filename=name,
                content_type=ALLOWED[ext],
                data=data,
                size=len(data),
                uploaded_by_id=getattr(current_user, "id", None),
            )
        )
        count += 1
    return count


def _image_to_pdf(data: bytes) -> io.BytesIO:
    img = Image.open(io.BytesIO(data))
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, "white")
        bg.paste(img, mask=img.split()[-1])
        img = bg
    else:
        img = img.convert("RGB")
    out = io.BytesIO()
    img.save(out, format="PDF", resolution=150.0)
    out.seek(0)
    return out


def merge_with_documents(main_pdf, documents) -> io.BytesIO:
    """Return the requisition PDF followed by every supporting document."""
    documents = list(documents)
    if hasattr(main_pdf, "seek"):
        main_pdf.seek(0)
    if not documents:
        return main_pdf
    writer = PdfWriter()
    writer.append(PdfReader(main_pdf))
    for doc in documents:
        try:
            if doc.content_type == "application/pdf":
                reader = PdfReader(io.BytesIO(doc.data))
                if reader.is_encrypted:
                    reader.decrypt("")
            else:
                reader = PdfReader(_image_to_pdf(doc.data))
            writer.append(reader)
        except Exception:
            continue  # skip unreadable document rather than fail the download
    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out
