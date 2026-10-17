"""Report builders for requisition CSV and Excel exports."""
import csv
import io
import os

from flask import current_app

BRAND_RED = 'D21F3C'
BRAND_BLACK = '1A1A1A'

COMPANY_NAME = 'First Mutual Life Assurance Company'
AMOUNT_INDEX = 7

COLUMNS = [
    ('Requisition No', lambda r: r.requisition_number),
    ('Status', lambda r: r.status.replace('_', ' ').title()),
    ('Payee', lambda r: r.in_favor_of or ''),
    ('Bank', lambda r: r.bank_name or ''),
    ('Branch', lambda r: r.branch or ''),
    ('Account No', lambda r: r.account_number or ''),
    ('Currency', lambda r: r.currency or ''),
    ('Amount', lambda r: f"{(r.total_debit or 0):.2f}"),
    ('Initiator', lambda r: r.initiator.full_name if r.initiator else ''),
    ('Reviewer', lambda r: r.reviewer.full_name if r.reviewer else ''),
    ('Approvals', lambda r: f"{r.current_approvals or 0}/{r.required_approvals or 0}"),
    ('Departments', lambda r: ', '.join(sorted({i.account_department for i in r.items if i.account_department}))),
    ('Created', lambda r: r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else ''),
    ('Completed', lambda r: r.completed_at.strftime('%Y-%m-%d %H:%M') if r.completed_at else ''),
]


def logo_path():
    return os.path.join(current_app.root_path, 'static', 'images', 'logo.png')


def build_rows(requisitions):
    headers = [header for header, _getter in COLUMNS]
    rows = [[getter(r) for _header, getter in COLUMNS] for r in requisitions]
    return headers, rows


def totals_by_currency(requisitions):
    totals = {}
    for r in requisitions:
        code = r.currency or ''
        totals[code] = totals.get(code, 0) + (r.total_debit or 0)
    if not totals:
        return '-'
    return ' | '.join(f"{code} {totals[code]:,.2f}" for code in sorted(totals))


def describe_filters(filters):
    parts = []
    if filters.get('status'):
        parts.append(f"Status: {filters['status']}")
    if filters.get('currency'):
        parts.append(f"Currency: {filters['currency']}")
    if filters.get('department'):
        parts.append(f"Department: {filters['department']}")
    if filters.get('initiator_name'):
        parts.append(f"Initiator: {filters['initiator_name']}")
    if filters.get('date_from'):
        parts.append(f"From: {filters['date_from']}")
    if filters.get('date_to'):
        parts.append(f"To: {filters['date_to']}")
    return '; '.join(parts) if parts else 'All records'


def to_csv(requisitions, meta):
    text = io.StringIO()
    writer = csv.writer(text)
    writer.writerow([f"{COMPANY_NAME.upper()} - REQUISITION REPORT"])
    writer.writerow(['====================================================='])
    writer.writerow([COMPANY_NAME])
    writer.writerow(['Requisition Report'])
    writer.writerow([f"Generated: {meta['generated']}"])
    writer.writerow([f"Filters: {meta['filters']}"])
    writer.writerow([])
    headers, rows = build_rows(requisitions)
    writer.writerow(headers)
    writer.writerows(rows)
    buf = io.BytesIO(('\ufeff' + text.getvalue()).encode('utf-8'))
    buf.seek(0)
    return buf


def to_excel(requisitions, meta):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = 'Requisitions'
    ws.sheet_view.showGridLines = False

    last_col = 14  # A..N

    # Logo (optional, loaded from bytes so it works reliably in the container)
    try:
        from openpyxl.drawing.image import Image as XLImage
        with open(logo_path(), 'rb') as fh:
            logo_bytes = io.BytesIO(fh.read())
        img = XLImage(logo_bytes)
        target_h = 70
        ratio = img.width / img.height if img.height else 1
        img.height = target_h
        img.width = int(target_h * ratio)
        ws.add_image(img, 'A1')
    except Exception as exc:
        current_app.logger.warning('Excel report logo not added: %s', exc)

    # Banner: logo sits in A1:B4, text is merged across C:N
    ws.column_dimensions['A'].width = 14
    ws.column_dimensions['B'].width = 14
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 20
    ws.row_dimensions[3].height = 16
    ws.row_dimensions[4].height = 16

    text_align = Alignment(horizontal='left', vertical='center')
    banner = [
        (1, COMPANY_NAME, Font(bold=True, size=16, color=BRAND_RED)),
        (2, 'Requisition Report', Font(bold=True, size=12)),
        (3, f"Generated: {meta['generated']}", Font(size=9, color='666666')),
        (4, f"Filters: {meta['filters']}", Font(size=9, color='666666')),
    ]
    for row_idx, text, font in banner:
        ws.merge_cells(start_row=row_idx, start_column=3, end_row=row_idx, end_column=last_col)
        cell = ws.cell(row=row_idx, column=3, value=text)
        cell.font = font
        cell.alignment = text_align

    # Thick red rule under the banner
    red_side = Side(style='medium', color=BRAND_RED)
    for col in range(1, last_col + 1):
        ws.cell(row=4, column=col).border = Border(bottom=red_side)

    side = Side(style='thin', color='D0D0D0')
    border = Border(left=side, right=side, top=side, bottom=side)

    headers, rows = build_rows(requisitions)
    header_row = 6
    ws.row_dimensions[header_row].height = 30
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col, value=header)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill(start_color=BRAND_BLACK, end_color=BRAND_BLACK, fill_type='solid')
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = border
        ws.column_dimensions[get_column_letter(col)].width = max(14, len(header) + 4)
    # Keep the logo columns at a fixed width
    ws.column_dimensions['A'].width = 14
    ws.column_dimensions['B'].width = 14

    zebra_fill = PatternFill(start_color='F8F8F8', end_color='F8F8F8', fill_type='solid')
    first_data = header_row + 1
    row_num = first_data
    for idx, row in enumerate(rows, start=1):
        for col, value in enumerate(row, start=1):
            if col - 1 == AMOUNT_INDEX:
                # Write a real number so the SUM total works
                value = float(value)
            cell = ws.cell(row=row_num, column=col, value=value)
            cell.border = border
            if idx % 2 == 0:
                cell.fill = zebra_fill
            if col - 1 == AMOUNT_INDEX:
                cell.number_format = '#,##0.00'
        row_num += 1

    ws.freeze_panes = 'A7'

    # Totals row
    last = row_num - 1
    amount_letter = get_column_letter(AMOUNT_INDEX + 1)
    total_fill = PatternFill(start_color='FCE8EA', end_color='FCE8EA', fill_type='solid')
    for col in range(1, last_col + 1):
        cell = ws.cell(row=row_num, column=col)
        cell.fill = total_fill
        cell.font = Font(bold=True)
        cell.border = border
    ws.cell(row=row_num, column=1, value='TOTAL')
    total_cell = ws.cell(row=row_num, column=AMOUNT_INDEX + 1,
                         value=f"=SUM({amount_letter}{first_data}:{amount_letter}{last})")
    total_cell.number_format = '#,##0.00'

    # Print setup
    from openpyxl.worksheet.properties import PageSetupProperties
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    if ws.sheet_properties.pageSetUpPr is None:
        ws.sheet_properties.pageSetUpPr = PageSetupProperties()
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = '6:6'

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf

