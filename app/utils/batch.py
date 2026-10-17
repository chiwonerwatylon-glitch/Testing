"""Stanbic Business Online batch files: CSV upload and Excel copy.

Each row is (requisition, reference, account_name). Files contain data rows only, with no headings.
Columns: Account Name, Account Number, Code, Amount, Reference, Currency Code, Branch Name.
"""
import csv
import io
from decimal import Decimal, ROUND_HALF_UP

ACCOUNT_NUMBER_PREFIX = "'"  # forces the account number to stay as typed text in Excel and CSV


def money(value):
    """Round to two decimal places (half up), e.g. 1234.5 -> Decimal('1234.50')."""
    return Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def payment_code(requisition):
    """'Code' column: the account code of the first line item on the requisition."""
    first = requisition.items.first()
    return first.account_code if first else ''


def _flat(text):
    return ' '.join(str(text or '').split())


def default_reference(requisition):
    """Reference defaults to the reason for payment, flattened to one line."""
    return (_flat(requisition.reason_for_payment) or requisition.requisition_number)[:255]


def default_account_name(requisition):
    return (_flat(requisition.in_favor_of))[:200]


def clean_text(value, fallback, limit):
    text = _flat(value)[:limit]
    return text or fallback


def account_number_text(requisition):
    number = _flat(requisition.account_number)
    return f"{ACCOUNT_NUMBER_PREFIX}{number}" if number else ''


def batch_row(requisition, reference, account_name):
    return [
        account_name or requisition.in_favor_of or '',           # Account Name
        account_number_text(requisition),                        # Account Number, text
        payment_code(requisition),                               # Code
        money(requisition.total_debit),                          # Amount, 2 dp
        reference or requisition.requisition_number,             # Reference
        requisition.currency or '',                              # Currency Code
        requisition.branch or '',                                # Branch Name
    ]


AMOUNT_INDEX = 3


def to_batch_csv(rows):
    text = io.StringIO()
    writer = csv.writer(text)
    for requisition, reference, account_name in rows:
        values = batch_row(requisition, reference, account_name)
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

    for row_idx, (requisition, reference, account_name) in enumerate(rows, start=1):
        values = batch_row(requisition, reference, account_name)
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=row_idx, column=col)
            if col - 1 == AMOUNT_INDEX:
                cell.value = float(value)
                cell.number_format = '0.00'
                cell.alignment = Alignment(horizontal='right')
            else:
                cell.value = str(value)
                cell.number_format = '@'  # text, so the account number keeps every digit

    for idx, width in enumerate([28, 20, 14, 14, 18, 14, 24], start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf

