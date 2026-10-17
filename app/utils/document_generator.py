from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
import csv
import io
import os
from flask import current_app
from datetime import datetime

# FML Brand Colors
FML_RED = colors.HexColor('#D21F3C')
FML_BLACK = colors.HexColor('#1A1A1A')
FML_RED_HEX = 'D21F3C'
FML_BLACK_HEX = '1A1A1A'

class RequisitionDocumentGenerator:
    
    def __init__(self, requisition):
        self.requisition = requisition
        self.logo_path = os.path.join(current_app.root_path, 'static', 'images', 'logo.png')
    
    def generate_pdf(self):
        """Generate PDF version of requisition"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, 
                               rightMargin=1*cm, leftMargin=1*cm,
                               topMargin=1*cm, bottomMargin=1*cm)
        
        styles = getSampleStyleSheet()
        elements = []
        
        # Custom styles - FML Red & Black theme
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=FML_BLACK,
            alignment=TA_CENTER,
            spaceAfter=10
        )
        
        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Normal'],
            fontSize=12,
            textColor=FML_RED,
            alignment=TA_CENTER,
            spaceAfter=10,
            fontName='Helvetica-Bold'
        )
        
        ref_style = ParagraphStyle(
            'RefStyle',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
            spaceAfter=15
        )
        
        # Header with logo
        if os.path.exists(self.logo_path):
            logo = Image(self.logo_path, width=2*inch, height=0.8*inch)
            elements.append(logo)
        
        elements.append(Paragraph("FIRST MUTUAL LIFE ASSURANCE COMPANY", title_style))
        elements.append(Paragraph("PAYMENT REQUISITION", subtitle_style))
        elements.append(Paragraph(f"Requisition No: {self.requisition.requisition_number}", ref_style))
        
        # Red divider line
        elements.append(Table([['']],  colWidths=[7*inch], style=TableStyle([
            ('LINEBELOW', (0,0), (-1,-1), 2, FML_RED),
        ])))
        elements.append(Spacer(1, 0.3*inch))
        
        # Payment details
        payment_data = [
            ['In Favor Of:', self.requisition.in_favor_of],
            ['Bank:', self.requisition.bank_name],
            ['Branch:', self.requisition.branch],
            ['Account Number:', self.requisition.account_number],
            ['Reason for Payment:', self.requisition.reason_for_payment],
            ['ITF 263:', self.requisition.itf_263],
        ]
        
        payment_table = Table(payment_data, colWidths=[2.5*inch, 4.5*inch])
        payment_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8F8F8')),
        ]))
        elements.append(payment_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Items table
        items_header = ['Account Name', 'Account Code', 'Location', 'Department', 'Details', 'Debit', 'Credit']
        items_data = [items_header]
        
        for item in self.requisition.items:
            items_data.append([
                item.account_name,
                item.account_code,
                item.account_location or '',
                item.account_department or '',
                item.details or '',
                f"${item.debit:,.2f}" if item.debit else '',
                f"${item.credit:,.2f}" if item.credit else ''
            ])
        
        # Totals row
        items_data.append(['', '', '', '', 'TOTALS',
                         f"${self.requisition.total_debit:,.2f}",
                         f"${self.requisition.total_credit:,.2f}"])
        
        items_table = Table(items_data, colWidths=[1.2*inch, 0.9*inch, 0.8*inch, 0.9*inch, 1.3*inch, 0.9*inch, 0.9*inch])
        items_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 0), (-1, 0), FML_BLACK),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (5, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FCE8EA')),
            ('TEXTCOLOR', (0, -1), (-1, -1), FML_RED),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 0.5*inch))
        
        # Signatures section
        auth_style = ParagraphStyle(
            'AuthStyle',
            parent=styles['Heading3'],
            textColor=FML_RED,
        )
        elements.append(Paragraph("<b>AUTHORIZATION</b>", auth_style))
        elements.append(Spacer(1, 0.2*inch))
        
        sig_data = self._get_signature_data()
        sig_table = Table(sig_data, colWidths=[2.5*inch, 2.5*inch, 2*inch])
        sig_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, 0), FML_BLACK),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ]))
        elements.append(sig_table)
        
        # Footer
        elements.append(Spacer(1, 0.3*inch))
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
        elements.append(Paragraph("This is a system-generated document from First Mutual Life Assurance Company Requisition System", footer_style))
        
        doc.build(elements)
        buffer.seek(0)
        return buffer
    
    def generate_docx(self):
        """Generate DOCX version of requisition"""
        doc = Document()
        
        # Set margins
        sections = doc.sections
        for section in sections:
            section.top_margin = Cm(1.5)
            section.bottom_margin = Cm(1.5)
            section.left_margin = Cm(2)
            section.right_margin = Cm(2)
        
        # Header
        header_para = doc.add_paragraph()
        header_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        if os.path.exists(self.logo_path):
            run = header_para.add_run()
            run.add_picture(self.logo_path, width=Inches(2))
        
        title = doc.add_paragraph('FIRST MUTUAL LIFE ASSURANCE COMPANY')
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_run = title.runs[0]
        title_run.bold = True
        title_run.font.size = Pt(18)
        title_run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)  # Black
        
        subtitle = doc.add_paragraph('PAYMENT REQUISITION')
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        subtitle_run = subtitle.runs[0]
        subtitle_run.bold = True
        subtitle_run.font.size = Pt(14)
        subtitle_run.font.color.rgb = RGBColor(0xD2, 0x1F, 0x3C)  # Red
        
        req_num = doc.add_paragraph(f'Requisition No: {self.requisition.requisition_number}')
        req_num.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        doc.add_paragraph()
        
        # Payment details table
        payment_table = doc.add_table(rows=6, cols=2)
        payment_table.style = 'Table Grid'
        
        payment_data = [
            ('In Favor Of:', self.requisition.in_favor_of),
            ('Bank:', self.requisition.bank_name),
            ('Branch:', self.requisition.branch),
            ('Account Number:', self.requisition.account_number),
            ('Reason for Payment:', self.requisition.reason_for_payment),
            ('ITF 263:', self.requisition.itf_263),
        ]
        
        for i, (label, value) in enumerate(payment_data):
            payment_table.rows[i].cells[0].text = label
            payment_table.rows[i].cells[1].text = str(value)
            payment_table.rows[i].cells[0].paragraphs[0].runs[0].bold = True
        
        doc.add_paragraph()
        
        # Items table
        items = list(self.requisition.items)
        items_table = doc.add_table(rows=len(items) + 2, cols=7)
        items_table.style = 'Table Grid'
        
        headers = ['Account Name', 'Account Code', 'Location', 'Department', 'Details', 'Debit', 'Credit']
        header_row = items_table.rows[0]
        for i, header in enumerate(headers):
            header_row.cells[i].text = header
            run = header_row.cells[i].paragraphs[0].runs[0]
            run.bold = True
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            # Set black background for header cell
            shading_elm = header_row.cells[i]._element
            from docx.oxml.ns import qn
            from docx.oxml import OxmlElement
            shd = OxmlElement('w:shd')
            shd.set(qn('w:fill'), '1A1A1A')
            shading_elm.get_or_add_tcPr().append(shd)
        
        for i, item in enumerate(items, 1):
            row = items_table.rows[i]
            row.cells[0].text = item.account_name
            row.cells[1].text = item.account_code
            row.cells[2].text = item.account_location or ''
            row.cells[3].text = item.account_department or ''
            row.cells[4].text = item.details or ''
            row.cells[5].text = f"${item.debit:,.2f}" if item.debit else ''
            row.cells[6].text = f"${item.credit:,.2f}" if item.credit else ''
        
        # Totals row
        totals_row = items_table.rows[-1]
        totals_row.cells[4].text = 'TOTALS'
        totals_row.cells[5].text = f"${self.requisition.total_debit:,.2f}"
        totals_row.cells[6].text = f"${self.requisition.total_credit:,.2f}"
        for cell in totals_row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.bold = True
                    run.font.color.rgb = RGBColor(0xD2, 0x1F, 0x3C)
        
        doc.add_paragraph()
        auth_para = doc.add_paragraph('AUTHORIZATION')
        auth_para.runs[0].bold = True
        auth_para.runs[0].font.color.rgb = RGBColor(0xD2, 0x1F, 0x3C)
        auth_para.runs[0].font.size = Pt(13)
        
        # Signatures
        self._add_docx_signatures(doc)
        
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer
    
    def generate_excel(self):
        """Generate Excel version of requisition"""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Requisition"
        
        # Styles - FML Red & Black Theme
        header_font = Font(bold=True, size=14, color='1A1A1A')
        subheader_font = Font(bold=True, size=11, color='D21F3C')
        border = Border(
            left=Side(style='thin', color='CCCCCC'),
            right=Side(style='thin', color='CCCCCC'),
            top=Side(style='thin', color='CCCCCC'),
            bottom=Side(style='thin', color='CCCCCC')
        )
        header_fill = PatternFill(start_color='1A1A1A', end_color='1A1A1A', fill_type='solid')
        header_font_white = Font(bold=True, color='FFFFFF')
        totals_fill = PatternFill(start_color='FCE8EA', end_color='FCE8EA', fill_type='solid')
        totals_font = Font(bold=True, color='D21F3C')
        
        # Title
        ws.merge_cells('A1:G1')
        ws['A1'] = 'FIRST MUTUAL LIFE ASSURANCE COMPANY'
        ws['A1'].font = header_font
        ws['A1'].alignment = Alignment(horizontal='center')
        
        ws.merge_cells('A2:G2')
        ws['A2'] = 'PAYMENT REQUISITION'
        ws['A2'].font = subheader_font
        ws['A2'].alignment = Alignment(horizontal='center')
        
        ws.merge_cells('A3:G3')
        ws['A3'] = f'Requisition No: {self.requisition.requisition_number}'
        ws['A3'].alignment = Alignment(horizontal='center')
        
        # Payment details
        row = 5
        payment_data = [
            ('In Favor Of:', self.requisition.in_favor_of),
            ('Bank:', self.requisition.bank_name),
            ('Branch:', self.requisition.branch),
            ('Account Number:', self.requisition.account_number),
            ('Reason for Payment:', self.requisition.reason_for_payment),
            ('ITF 263:', self.requisition.itf_263),
        ]
        
        for label, value in payment_data:
            ws[f'A{row}'] = label
            ws[f'A{row}'].font = Font(bold=True)
            ws[f'B{row}'] = value
            ws[f'A{row}'].border = border
            ws[f'B{row}'].border = border
            row += 1
        
        row += 1
        
        # Items header
        headers = ['Account Name', 'Account Code', 'Location', 'Department', 'Details', 'Debit', 'Credit']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = header_font_white
            cell.fill = header_fill
            cell.border = border
            cell.alignment = Alignment(horizontal='center')
        
        row += 1
        
        # Items
        for item in self.requisition.items:
            ws.cell(row=row, column=1, value=item.account_name).border = border
            ws.cell(row=row, column=2, value=item.account_code).border = border
            ws.cell(row=row, column=3, value=item.account_location or '').border = border
            ws.cell(row=row, column=4, value=item.account_department or '').border = border
            ws.cell(row=row, column=5, value=item.details or '').border = border
            ws.cell(row=row, column=6, value=item.debit if item.debit else '').border = border
            ws.cell(row=row, column=7, value=item.credit if item.credit else '').border = border
            row += 1
        
        # Totals
        for col in range(1, 8):
            ws.cell(row=row, column=col).fill = totals_fill
        ws.cell(row=row, column=5, value='TOTALS').font = totals_font
        ws.cell(row=row, column=6, value=self.requisition.total_debit).font = totals_font
        ws.cell(row=row, column=7, value=self.requisition.total_credit).font = totals_font
        
        # Column widths
        ws.column_dimensions['A'].width = 20
        ws.column_dimensions['B'].width = 15
        ws.column_dimensions['C'].width = 15
        ws.column_dimensions['D'].width = 15
        ws.column_dimensions['E'].width = 25
        ws.column_dimensions['F'].width = 12
        ws.column_dimensions['G'].width = 12
        
        row += 2
        
        # Signatures
        ws[f'A{row}'] = 'AUTHORIZATION'
        ws[f'A{row}'].font = Font(bold=True, size=12, color='D21F3C')
        row += 1
        
        self._add_excel_signatures(ws, row)
        
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer
    
    def generate_csv(self):
        """Generate CSV version of requisition"""
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        
        # Header info
        writer.writerow(['FIRST MUTUAL LIFE ASSURANCE COMPANY'])
        writer.writerow(['PAYMENT REQUISITION'])
        writer.writerow([f'Requisition No: {self.requisition.requisition_number}'])
        writer.writerow([])
        
        # Payment details
        writer.writerow(['In Favor Of:', self.requisition.in_favor_of])
        writer.writerow(['Bank:', self.requisition.bank_name])
        writer.writerow(['Branch:', self.requisition.branch])
        writer.writerow(['Account Number:', self.requisition.account_number])
        writer.writerow(['Reason for Payment:', self.requisition.reason_for_payment])
        writer.writerow(['ITF 263:', self.requisition.itf_263])
        writer.writerow([])
        
        # Items
        writer.writerow(['Account Name', 'Account Code', 'Location', 'Department', 'Details', 'Debit', 'Credit'])
        for item in self.requisition.items:
            writer.writerow([
                item.account_name,
                item.account_code,
                item.account_location or '',
                item.account_department or '',
                item.details or '',
                item.debit if item.debit else '',
                item.credit if item.credit else ''
            ])
        
        writer.writerow(['', '', '', '', 'TOTALS', self.requisition.total_debit, self.requisition.total_credit])
        writer.writerow([])
        
        # Signatures
        writer.writerow(['AUTHORIZATION'])
        writer.writerow(['Role', 'Name', 'Date Signed'])
        writer.writerow(['Initiated By', self.requisition.initiator.full_name, 
                        self.requisition.initiated_at.strftime('%Y-%m-%d %H:%M') if self.requisition.initiated_at else ''])
        
        if self.requisition.reviewer:
            writer.writerow(['Reviewed By', self.requisition.reviewer.full_name,
                           self.requisition.reviewed_at.strftime('%Y-%m-%d %H:%M') if self.requisition.reviewed_at else ''])
        
        from app.models import ApprovalLog
        for log in self.requisition.approval_logs.filter_by(action='approved').order_by(ApprovalLog.approval_level):
            writer.writerow([f'Approver {log.approval_level}', log.approver.full_name,
                           log.created_at.strftime('%Y-%m-%d %H:%M')])
        
        # Convert to bytes
        buffer.seek(0)
        bytes_buffer = io.BytesIO()
        bytes_buffer.write(buffer.getvalue().encode('utf-8'))
        bytes_buffer.seek(0)
        return bytes_buffer
    
    def _get_signature_data(self):
        """Get signature data for PDF table"""
        from app.models import ApprovalLog
        
        data = [
            ['Role', 'Name & Signature', 'Date Signed'],
            ['Initiated By:', self.requisition.initiator.full_name,
             self.requisition.initiated_at.strftime('%Y-%m-%d %H:%M') if self.requisition.initiated_at else ''],
        ]
        
        if self.requisition.reviewer:
            data.append(['Reviewed By:', self.requisition.reviewer.full_name,
                        self.requisition.reviewed_at.strftime('%Y-%m-%d %H:%M') if self.requisition.reviewed_at else ''])
        else:
            data.append(['Reviewed By:', '________________', '________________'])
        
        approval_logs = list(self.requisition.approval_logs.filter_by(action='approved').order_by(ApprovalLog.approval_level))
        
        for i in range(1, self.requisition.required_approvals + 1):
            approver_log = next((log for log in approval_logs if log.approval_level == i), None)
            if approver_log:
                data.append([f'Approver {i}:', approver_log.approver.full_name,
                           approver_log.created_at.strftime('%Y-%m-%d %H:%M')])
            else:
                data.append([f'Approver {i}:', '________________', '________________'])
        
        return data
    
    def _add_docx_signatures(self, doc):
        """Add signatures section to DOCX"""
        from app.models import ApprovalLog
        
        sig_table = doc.add_table(rows=2 + self.requisition.required_approvals + (1 if self.requisition.reviewer else 0), cols=3)
        sig_table.style = 'Table Grid'
        
        # Header
        sig_table.rows[0].cells[0].text = 'Role'
        sig_table.rows[0].cells[1].text = 'Name & Signature'
        sig_table.rows[0].cells[2].text = 'Date Signed'
        
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
        for cell in sig_table.rows[0].cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.bold = True
                    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            shd = OxmlElement('w:shd')
            shd.set(qn('w:fill'), '1A1A1A')
            cell._element.get_or_add_tcPr().append(shd)
        
        # Initiator
        sig_table.rows[1].cells[0].text = 'Initiated By:'
        sig_table.rows[1].cells[1].text = self.requisition.initiator.full_name
        sig_table.rows[1].cells[2].text = self.requisition.initiated_at.strftime('%Y-%m-%d %H:%M') if self.requisition.initiated_at else ''
        
        row_idx = 2
        
        # Reviewer
        if self.requisition.reviewer:
            sig_table.rows[row_idx].cells[0].text = 'Reviewed By:'
            sig_table.rows[row_idx].cells[1].text = self.requisition.reviewer.full_name
            sig_table.rows[row_idx].cells[2].text = self.requisition.reviewed_at.strftime('%Y-%m-%d %H:%M') if self.requisition.reviewed_at else ''
            row_idx += 1
        
        # Approvers
        approval_logs = list(self.requisition.approval_logs.filter_by(action='approved').order_by(ApprovalLog.approval_level))
        
        for i in range(1, self.requisition.required_approvals + 1):
            approver_log = next((log for log in approval_logs if log.approval_level == i), None)
            if approver_log:
                sig_table.rows[row_idx].cells[0].text = f'Approver {i}:'
                sig_table.rows[row_idx].cells[1].text = approver_log.approver.full_name
                sig_table.rows[row_idx].cells[2].text = approver_log.created_at.strftime('%Y-%m-%d %H:%M')
            else:
                sig_table.rows[row_idx].cells[0].text = f'Approver {i}:'
                sig_table.rows[row_idx].cells[1].text = '________________'
                sig_table.rows[row_idx].cells[2].text = '________________'
            row_idx += 1
    
    def _add_excel_signatures(self, ws, start_row):
        """Add signatures section to Excel"""
        from app.models import ApprovalLog
        
        header_fill = PatternFill(start_color='1A1A1A', end_color='1A1A1A', fill_type='solid')
        header_font_white = Font(bold=True, color='FFFFFF')
        
        row = start_row
        headers = ['Role', 'Name & Signature', 'Date Signed']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = header_font_white
            cell.fill = header_fill
        
        row += 1
        ws.cell(row=row, column=1, value='Initiated By:')
        ws.cell(row=row, column=2, value=self.requisition.initiator.full_name)
        ws.cell(row=row, column=3, value=self.requisition.initiated_at.strftime('%Y-%m-%d %H:%M') if self.requisition.initiated_at else '')
        
        row += 1
        if self.requisition.reviewer:
            ws.cell(row=row, column=1, value='Reviewed By:')
            ws.cell(row=row, column=2, value=self.requisition.reviewer.full_name)
            ws.cell(row=row, column=3, value=self.requisition.reviewed_at.strftime('%Y-%m-%d %H:%M') if self.requisition.reviewed_at else '')
            row += 1
        
        approval_logs = list(self.requisition.approval_logs.filter_by(action='approved').order_by(ApprovalLog.approval_level))
        
        for i in range(1, self.requisition.required_approvals + 1):
            approver_log = next((log for log in approval_logs if log.approval_level == i), None)
            ws.cell(row=row, column=1, value=f'Approver {i}:')
            if approver_log:
                ws.cell(row=row, column=2, value=approver_log.approver.full_name)
                ws.cell(row=row, column=3, value=approver_log.created_at.strftime('%Y-%m-%d %H:%M'))
            else:
                ws.cell(row=row, column=2, value='________________')
                ws.cell(row=row, column=3, value='________________')
            row += 1
