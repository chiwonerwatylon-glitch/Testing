"""
Stanbic Business Online batch files: CSV upload and Excel copy.

Each row is (requisition, reference, account_name, code).

Generated files contain data rows only (no headings).
Columns (in order):
- Account Name
- Account Number
- Code
- Amount
- Reference
- Currency Code
- Branch Name
"""

from __future__ import annotations

import csv
import io
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, List, Sequence, Tuple, Any

ACCOUNT_NUMBER_PREFIX = "'"  # forces the account number to stay as typed text in Excel and CSV
AMOUNT_INDEX = 3  # index of Amount column in the row list


def money(value: Any) -> Decimal:
    """Round to two decimal places (half up), e.g. 1234.5 -> Decimal('1234.50')."""
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def net_amount(requisition) -> Decimal:
    """Net payment amount: total credit minus total debit, as a 2 dp Decimal."""
    credit = Decimal(str(requisition.total_credit or 0))
    debit = Decimal(str(requisition.total_debit or 0))
    return money(credit - debit)


def payment_code(requisition) -> str:
    """'Code' column: the account code of the first line item on the requisition."""
    first = requisition.items.first()
    return first.account_code if first else ""


def _flat(text: Any) -> str:
    """Flatten whitespace in text to single spaces."""
    return " ".join(str(text or "").split())


def default_reference(requisition) -> str:
    """Reference defaults to the reason for payment, flattened to one line."""
    return (_flat(requisition.reason_for_payment) or requisition.requisition_number)[:255]


def default_account_name(requisition) -> str:
    """Default account name, truncated to 200 characters."""
    return _flat(requisition.in_favor_of)[:200]


def clean_text(value: Any, fallback: str, limit: int) -> str:
    """Normalize text to one line, truncate, and apply fallback if empty."""
    text = _flat(value)[:limit]
    return text or fallback


def account_number_text(requisition) -> str:
    """Account number prefixed to keep it as text in Excel/CSV."""
    number = _flat(requisition.account_number)
    return f"{ACCOUNT_NUMBER_PREFIX}{number}" if number else ""


def batch_row(requisition, reference: str, account_name: str, code: str) -> List[Any]:
    """Return a single row in the Stanbic batch format."""
    return [
        account_name or requisition.in_favor_of or "",     # Account Name
        account_number_text(requisition),                  # Account Number, text
        code or payment_code(requisition),                 # Code
        net_amount(requisition),                           # Amount, credit minus debit, 2 dp
        reference or requisition.requisition_number,       # Reference
        requisition.currency or "",                        # Currency Code
        requisition.branch or "",                          # Branch Name
    ]


def to_batch_csv(
    rows: Iterable[Tuple[Any, str, str, str]]
) -> io.BytesIO:
    """Generate CSV bytes buffer for Stanbic batch.

    rows: iterable of (requisition, reference, account_name, code)
    """
    text_io = io.StringIO()
    writer = csv.writer(text_io)

    for requisition, reference, account_name, code in rows:
        values: List[Any] = batch_row(requisition, reference, account_name, code)
        # Ensure amount is rendered as 2-decimal string
        values[AMOUNT_INDEX] = f"{values[AMOUNT_INDEX]:.2f}"
        writer.writerow(values)

    buf = io.BytesIO(text_io.getvalue().encode("utf-8"))
    buf.seek(0)
    return buf


def to_batch_excel(
    rows: Iterable[Tuple[Any, str, str, str]]
) -> io.BytesIO:
    """Generate an Excel (XLSX) buffer for Stanbic batch.

    rows: iterable of (requisition, reference, account_name, code)
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Batch"

    for row_idx, (requisition, reference, account_name, code) in enumerate(rows, start=1):
        values: Sequence[Any] = batch_row(requisition, reference, account_name, code)
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=row_idx, column=col)
            if col - 1 == AMOUNT_INDEX:
                cell.value = float(value)
                cell.number_format = "0.00"
                cell.alignment = Alignment(horizontal="right")
            else:
                cell.value = str(value)
                # Format as text so account number keeps every digit
                cell.number_format = "@"

    # Reasonable column widths for readability
    for idx, width in enumerate([28, 20, 14, 14, 18, 14, 24], start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
