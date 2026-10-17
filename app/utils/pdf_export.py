import io
import os
from xml.sax.saxutils import escape

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.utils.reports import AMOUNT_INDEX, BRAND_BLACK, BRAND_RED, COMPANY_NAME, build_rows, totals_by_currency

WEIGHTS = [1.4, 1.2, 1.8, 1.2, 1.1, 1.3, 0.8, 1.1, 1.5, 1.5, 0.9, 1.2, 1.3, 1.3]


def _logo():
    return os.path.join(current_app.root_path, 'static', 'images', 'logo.png')


def to_pdf(requisitions, meta):
    page = landscape(A4)
    width, height = page
    red = colors.HexColor('#' + BRAND_RED)
    black = colors.HexColor('#' + BRAND_BLACK)
    grid = colors.HexColor('#D0D0D0')
    zebra = colors.HexColor('#F8F8F8')

    def draw_page(canvas, doc):
        canvas.saveState()
        try:
            canvas.drawImage(ImageReader(_logo()), 14 * mm, height - 27 * mm, width=22 * mm, height=22 * mm,
                             preserveAspectRatio=True, mask='auto')
        except Exception as exc:
            current_app.logger.warning('PDF report logo not added: %s', exc)
        canvas.setFillColor(red)
        canvas.setFont('Helvetica-Bold', 15)
        canvas.drawString(40 * mm, height - 16 * mm, COMPANY_NAME)
        canvas.setFillColor(black)
        canvas.setFont('Helvetica', 11)
        canvas.drawString(40 * mm, height - 22 * mm, 'Requisition Report')
        canvas.setStrokeColor(red)
        canvas.setLineWidth(2)
        canvas.line(14 * mm, height - 30 * mm, width - 14 * mm, height - 30 * mm)
        canvas.setStrokeColor(grid)
        canvas.setLineWidth(0.5)
        canvas.line(14 * mm, 12 * mm, width - 14 * mm, 12 * mm)
        canvas.setFont('Helvetica', 7.5)
        canvas.setFillColor(colors.HexColor('#666666'))
        canvas.drawString(14 * mm, 8 * mm, f"Generated {meta['generated']}  |  Filters: {meta['filters']}")
        canvas.drawRightString(width - 14 * mm, 8 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    cell = ParagraphStyle('cell', fontName='Helvetica', fontSize=7.2, leading=9)
    head = ParagraphStyle('head', fontName='Helvetica-Bold', fontSize=7.4, leading=9, textColor=colors.white)

    headers, rows = build_rows(requisitions)
    story = [
        Paragraph(
            f"<b>Requisitions:</b> {len(requisitions)} &nbsp;&nbsp; <b>Totals:</b> {escape(totals_by_currency(requisitions))}"
            f" &nbsp;&nbsp; <b>Generated:</b> {escape(meta['generated'])}",
            cell,
        ),
        Spacer(1, 5 * mm),
    ]

    data = [[Paragraph(escape(h), head) for h in headers]]
    if rows:
        for row in rows:
            data.append([Paragraph(escape(str(v)), cell) for v in row])
    else:
        data.append([Paragraph('No requisitions match these filters.', cell)] + [Paragraph('', cell)] * (len(headers) - 1))

    total = [Paragraph('<b>TOTAL</b>', cell)]
    total += [Paragraph('', cell)] * (AMOUNT_INDEX - 1)
    total += [Paragraph(f"<b>{escape(totals_by_currency(requisitions))}</b>", cell)]
    total += [Paragraph('', cell)] * (len(headers) - AMOUNT_INDEX - 1)
    data.append(total)

    usable = width - 28 * mm
    weights = WEIGHTS if len(WEIGHTS) == len(headers) else [1] * len(headers)
    col_widths = [usable * w / sum(weights) for w in weights]

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, grid),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, zebra]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FCE8EA')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(table)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=page, leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=36 * mm, bottomMargin=18 * mm,
                            title='Requisition Report', author=COMPANY_NAME)
    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    buf.seek(0)
    return buf
