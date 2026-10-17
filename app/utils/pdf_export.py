from __future__ import annotations

import io
import os
from typing import Any, Iterable, Tuple
from xml.sax.saxutils import escape

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.utils.reports import (
    AMOUNT_INDEX,
    BRAND_BLACK,
    BRAND_RED,
    COMPANY_NAME,
    build_rows,
    totals_by_currency,
)

# Column weights for report table; must match header count if used as-is
WEIGHTS = [1.4, 1.2, 1.8, 1.2, 1.1, 1.3, 0.8, 1.1, 1.5, 1.5, 0.9, 1.2, 1.3, 1.3]


def _logo_path() -> str:
    """Return absolute path to the company logo."""
    return os.path.join(current_app.root_path, "static", "images", "logo.png")


def to_pdf(requisitions: Iterable[Any], meta: dict[str, str]) -> io.BytesIO:
    """Generate a landscape A4 PDF requisition report for the given requisitions.

    Args:
        requisitions: An iterable of Requisition-like objects used by build_rows().
        meta: A dict with at least 'generated' and 'filters' strings.

    Returns:
        A BytesIO positioned at the beginning of the PDF content.
    """
    page = landscape(A4)
    width, height = page

    red = colors.HexColor("#" + BRAND_RED)
    black = colors.HexColor("#" + BRAND_BLACK)
    grid = colors.HexColor("#D0D0D0")
    zebra = colors.HexColor("#F8F8F8")

    def draw_page(canvas, doc) -> None:  # callback for reportlab
        canvas.saveState()
        try:
            canvas.drawImage(
                ImageReader(_logo_path()),
                14 * mm,
                height - 27 * mm,
                width=22 * mm,
                height=22 * mm,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception as exc:  # best-effort; do not break report
            current_app.logger.warning("PDF report logo not added: %s", exc)

        # Header text
        canvas.setFillColor(red)
        canvas.setFont("Helvetica-Bold", 15)
        canvas.drawString(40 * mm, height - 16 * mm, COMPANY_NAME)

        canvas.setFillColor(black)
        canvas.setFont("Helvetica", 11)
        canvas.drawString(40 * mm, height - 22 * mm, "Requisition Report")

        # Top red rule
        canvas.setStrokeColor(red)
        canvas.setLineWidth(2)
        canvas.line(14 * mm, height - 30 * mm, width - 14 * mm, height - 30 * mm)

        # Bottom grey rule
        canvas.setStrokeColor(grid)
        canvas.setLineWidth(0.5)
        canvas.line(14 * mm, 12 * mm, width - 14 * mm, 12 * mm)

        # Footer meta text
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(
            14 * mm,
            8 * mm,
            f"Generated {meta.get('generated', '')}  |  Filters: {meta.get('filters', '')}",
        )
        canvas.drawRightString(
            width - 14 * mm,
            8 * mm,
            f"Page {canvas.getPageNumber()}",
        )
        canvas.restoreState()

    # Styles
    cell_style = ParagraphStyle(
        "cell",
        fontName="Helvetica",
        fontSize=7.2,
        leading=9,
    )
    head_style = ParagraphStyle(
        "head",
        fontName="Helvetica-Bold",
        fontSize=7.4,
        leading=9,
        textColor=colors.white,
    )

    requisitions_list = list(requisitions)
    headers, rows = build_rows(requisitions_list)

    summary_text = (
        f"<b>Requisitions:</b> {len(requisitions_list)} "
        f"&nbsp;&nbsp; <b>Totals:</b> {escape(totals_by_currency(requisitions_list))} "
        f"&nbsp;&nbsp; <b>Generated:</b> {escape(meta.get('generated', ''))}"
    )

    story = [
        Paragraph(summary_text, cell_style),
        Spacer(1, 5 * mm),
    ]

    # Table data
    data: list[list[Paragraph]] = [
        [Paragraph(escape(h), head_style) for h in headers]
    ]

    if rows:
        for row in rows:
            data.append(
                [Paragraph(escape(str(v)), cell_style) for v in row]
            )
    else:
        # No data row: fill all columns with a message in first cell
        data.append(
            [Paragraph("No requisitions match these filters.", cell_style)]
            + [Paragraph("", cell_style)] * (len(headers) - 1)
        )

    # Totals row
    total_label = Paragraph("<b>TOTAL</b>", cell_style)
    total_value = Paragraph(
        f"<b>{escape(totals_by_currency(requisitions_list))}</b>",
        cell_style,
    )
    total_row: list[Paragraph] = [total_label]
    total_row += [Paragraph("", cell_style)] * (AMOUNT_INDEX - 1)
    total_row += [total_value]
    total_row += [Paragraph("", cell_style)] * (
        len(headers) - AMOUNT_INDEX - 1
    )
    data.append(total_row)

    # Column widths
    usable_width = width - 28 * mm
    if len(WEIGHTS) == len(headers):
        weights = WEIGHTS
    else:
        weights = [1.0] * len(headers)
    total_weight = sum(weights) or 1.0
    col_widths = [usable_width * w / total_weight for w in weights]

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.4, grid),
                ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, zebra]),
                (
                    "BACKGROUND",
                    (0, -1),
                    (-1, -1),
                    colors.HexColor("#FCE8EA"),
                ),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(table)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=page,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=36 * mm,
        bottomMargin=18 * mm,
        title="Requisition Report",
        author=COMPANY_NAME,
    )
    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    buf.seek(0)
    return buf
