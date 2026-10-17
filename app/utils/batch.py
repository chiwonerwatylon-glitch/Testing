"""Stanbic Business Online batch files: CSV upload and Excel copy.

Each row is (requisition, reference). Files contain data rows only, with no headings.
Columns: Account Name, Account Number, Code, Amount, Reference, Currency Code, Branch Name.
"""
import csv
import io
from decimal import Decimal, ROUND_HALF_UP


def money(value):
    """Round to two decimal places (half up), e.g. 1234.5 -> Decimal('1234.50')."""
    return Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def payment_code(requisition):
    """'Code' column: the account code of the first line item on the requisition."""
    first = requisition.items.first()
    return first.account_code if first else ''


def default_reference(requisition):
    """Reference defaults to the reason for payment, flattened to one line."""
    reason = ' '.join((requisition.reason_for_payment or '').split())
    return (reason or requisition.requisition_number)[:255]


def clean_reference(value, fallback):
    text = ' '.join(str(value or '').split())[:255]
    return text or fallback


def batch_row(requisition, reference):
    return [
        requisition.in_favor_of or '',          # Account Name  <- In Favor Of
        requisition.account_number or '',       # Account Number (text)
        payment_code(requisition),              # Code
        money(requisition.total_debit),         # Amount, 2 dp
        reference or requisition.requisition_number,  # Reference
        requisition.currency or '',             # Currency Code
        requisition.branch or '',               # Branch Name
    ]


AMOUNT_INDEX = 3
TEXT_INDEXES = (1, 2)  # account number and code keep their digits (no scientific notation or lost zeros)


def to_batch_csv(rows):
    text = io.StringIO()
    writer = csv.writer(text)
    for requisition, reference in rows:
        values = batch_row(requisition, reference)
        values[AMOUNT_INDEX] = f"{values[AMOUNT_INDEX]:.2f}"
        writer.writerow(values)
    buf = io.BytesIO(text.getvalue().encode('utf-8'))
    buf.seek(0)
    return buf


def to_batch_excel(rows):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = 'Batch'

    for row_idx, (requisition, reference) in enumerate(rows, start=1):
        values = batch_row(requisition, reference)
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=row_idx, column=col)
            if col - 1 == AMOUNT_INDEX:
                cell.value = float(value)
                cell.number_format = '0.00'
                cell.alignment = Alignment(horizontal='right')
            else:
                cell.value = str(value)
                cell.number_format = '@'  # text, so every digit of the account number shows

    for idx, width in enumerate([28, 20, 14, 14, 18, 14, 24], start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf

