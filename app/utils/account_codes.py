"""Excel template and import for the admin-managed account list (name, code, location)."""

from __future__ import annotations

import io
from typing import List, Tuple

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

HEADERS = ["Account Name", "Account Code", "Location"]


def build_template() -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "Accounts"
    ws.append(HEADERS)
    for c in ws[1]:
        c.font = Font(bold=True)
    for col, w in zip("ABC", (36, 20, 24)):
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=2, min_col=2, max_col=3):
        for c in row:
            c.number_format = "@"  # keep codes such as 00123 as typed
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return " ".join(str(value).split())


def parse_upload(file_obj) -> Tuple[List[dict], List[str]]:
    """Parse an uploaded workbook. Returns (rows, errors)."""
    try:
        wb = load_workbook(file_obj, read_only=True, data_only=True)
    except Exception:
        return [], ["The file is not a valid Excel (.xlsx) workbook."]
    ws = wb.active
    rows, errors, seen = [], [], set()
    it = ws.iter_rows(values_only=True)
    header = next(it, None)
    if not header or [_text(h).lower() for h in header[:3]] != [h.lower() for h in HEADERS]:
        return [], [
            "The first row must be the headings: " + ", ".join(HEADERS) + ". Download the template."
        ]
    for n, r in enumerate(it, start=2):
        r = list(r) + [None] * 3
        name, code, loc = (_text(v) for v in r[:3])
        if not (name or code or loc):
            continue
        if not (name and code):
            errors.append(f"Row {n}: Account Name and Account Code are required.")
        elif len(name) > 200 or len(code) > 50 or len(loc) > 100:
            errors.append(f"Row {n}: a value is too long.")
        elif (name, code, loc) not in seen:
            seen.add((name, code, loc))
            rows.append({"account_name": name, "account_code": code, "location": loc})
    if not rows and not errors:
        errors.append("The file has no data rows.")
    return rows, errors
