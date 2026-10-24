"""Build the two manuals as PDFs from docs/USER_MANUAL.md and docs/IT_GUIDE.md.

Usage:  pip install reportlab  &&  python docs/build_manuals.py
The text comes from the Markdown files; diagrams are drawn here.
"""
from __future__ import annotations

import os
import re

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate, Paragraph,
    Preformatted, Spacer, Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

HERE = os.path.dirname(os.path.abspath(__file__))
RED = colors.HexColor("#D21F3C")
BLACK = colors.HexColor("#1A1A1A")
GREY = colors.HexColor("#6B6B6B")
LIGHT = colors.HexColor("#F4F4F4")
GREEN = colors.HexColor("#198754")
DANGER = colors.HexColor("#DC3545")
BLUE = colors.HexColor("#2F6DB5")
AMBER = colors.HexColor("#E8A317")
W = 482  # usable width in points

# ----------------------------------------------------------------- diagram kit

def _wrap(text, n):
    out = []
    for part in text.split("\n"):
        words, line = part.split(), ""
        for w in words:
            if len(line) + len(w) + 1 > n and line:
                out.append(line)
                line = w
            else:
                line = f"{line} {w}".strip()
        out.append(line)
    return out


def box(d, x, y, w, h, text, fill=LIGHT, stroke=BLACK, color=BLACK, size=8, bold=False, dash=None):
    r = Rect(x, y, w, h, rx=5, ry=5, fillColor=fill, strokeColor=stroke, strokeWidth=1.1)
    if dash:
        r.strokeDashArray = dash
    d.add(r)
    lines = _wrap(text, max(6, int(w / (size * 0.52))))
    lh = size + 2
    top = y + h / 2 + (len(lines) * lh) / 2 - size + 1
    for i, ln in enumerate(lines):
        d.add(String(x + w / 2, top - i * lh, ln, textAnchor="middle", fontSize=size,
                     fillColor=color, fontName="Helvetica-Bold" if bold else "Helvetica"))


def label(d, x, y, text, size=7, color=GREY, anchor="middle", bold=False):
    for i, ln in enumerate(text.split("\n")):
        d.add(String(x, y - i * (size + 1.5), ln, textAnchor=anchor, fontSize=size, fillColor=color,
                     fontName="Helvetica-Bold" if bold else "Helvetica-Oblique"))


def arrow(d, pts, color=BLACK, dash=None, width=1.2):
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        ln = Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=width)
        if dash:
            ln.strokeDashArray = dash
        d.add(ln)
    (x1, y1), (x2, y2) = pts[-2], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    n = (dx * dx + dy * dy) ** 0.5 or 1
    ux, uy = dx / n, dy / n
    s = 5
    d.add(Polygon([x2, y2, x2 - ux * s * 1.6 - uy * s, y2 - uy * s * 1.6 + ux * s,
                   x2 - ux * s * 1.6 + uy * s, y2 - uy * s * 1.6 - ux * s],
                  fillColor=color, strokeColor=color, strokeWidth=0.5))


def title(d, text, y):
    d.add(String(W / 2, y, text, textAnchor="middle", fontSize=10, fillColor=RED, fontName="Helvetica-Bold"))


def mid(x, w):
    return x + w / 2

# ------------------------------------------------------------------- diagrams

def d_lifecycle():
    d = Drawing(W, 250)
    title(d, "Life of a requisition", 235)
    bw, bh, y = 68, 40, 170
    xs = [i * (bw + 14.8) for i in range(6)]
    names = ["Initiator\nsubmits", "Reviewer\nchecks", "Approver 1", "Approver 2",
             "Senior approver\n(USD 5,000+ only)", "APPROVED\n(NOT PAID)"]
    fills = [LIGHT, LIGHT, LIGHT, LIGHT, colors.HexColor("#FFF4D6"), colors.HexColor("#E3F3E8")]
    for x, n, f in zip(xs, names, fills):
        box(d, x, y, bw, bh, n, fill=f, bold=True, size=7.5)
    for i in range(5):
        arrow(d, [(xs[i] + bw, y + bh / 2), (xs[i + 1], y + bh / 2)], dash=[3, 2] if i == 3 else None)
    box(d, xs[5], 80, bw, 40, "PAID\nstamped green", fill=colors.HexColor("#CDEBD6"), stroke=GREEN, color=GREEN, bold=True, size=8)
    arrow(d, [(mid(xs[5], bw), y), (mid(xs[5], bw), 120)], color=GREEN)
    label(d, mid(xs[5], bw) - 4, 140, "initiator\nmarks Paid", anchor="end", size=6.5)
    box(d, 150, 20, 190, 36, "REJECTED  (reason recorded)", fill=colors.HexColor("#FBE3E5"), stroke=DANGER, color=DANGER, bold=True)
    for i in (1, 2, 3, 4):
        arrow(d, [(mid(xs[i], bw), y), (mid(xs[i], bw), 100), (mid(xs[i], bw) if False else 245, 100), (245, 56)] if False else [(mid(xs[i], bw), y), (mid(xs[i], bw), 62 + i * 8 if False else 70), ], color=DANGER, dash=[3, 2])
    # simple, readable reject routing: one bus line
    d.add(Line(mid(xs[1], bw), 70, mid(xs[4], bw), 70, strokeColor=DANGER, strokeWidth=1.2, strokeDashArray=[3, 2]))
    arrow(d, [(245, 70), (245, 56)], color=DANGER)
    label(d, 350, 40, "any reviewer or approver\ncan reject", anchor="start", size=6.5, color=DANGER)
    arrow(d, [(150, 38), (mid(xs[0], bw), 38), (mid(xs[0], bw), y)], color=DANGER)
    label(d, 30, 26, "initiator: Correct Mistakes and resubmit,\nor Delete", anchor="start", size=6.5, color=DANGER)
    return d


def d_register():
    d = Drawing(W, 120)
    title(d, "From registration to first use", 105)
    steps = ["Request an\naccount", "Account waits,\ninactive", "Administrator\nactivates and\nsets permissions", "Log in", "Upload your\nsignature\n(Profile)", "Ready to\nwork"]
    bw, g = 68, 14.8
    for i, s in enumerate(steps):
        x = i * (bw + g)
        box(d, x, 30, bw, 54, s, fill=colors.HexColor("#E3F3E8") if i == 5 else LIGHT, bold=(i == 2), size=7.5)
        if i:
            arrow(d, [(x - g, 57), (x, 57)])
    label(d, W / 2, 14, "Without a signature on file you cannot submit, review or approve.", size=7.5, color=RED)
    return d


def d_form():
    d = Drawing(W, 215)
    title(d, "The requisition form and where its choices come from", 200)
    box(d, 0, 120, 150, 60, "ADMINISTRATOR\nuploads Excel lists", fill=colors.HexColor("#FFF4D6"), stroke=AMBER, bold=True)
    box(d, 0, 30, 150, 60, "Paying banks list\nAccount list\n(name, code, location)", fill=LIGHT)
    arrow(d, [(75, 120), (75, 90)])
    form = [("1  Paying Bank", "pick from list, or Other"), ("2  Payment Details", "payee, currency, bank, branch,\naccount no, reason, ITF 263"),
            ("3  Account Details", "drop-downs: name, code, location\nDetails auto-fill (35 chars max)"), ("4  Supporting Documents", "PDF, PNG or JPG, 16 MB total")]
    for i, (h, t) in enumerate(form):
        y = 150 - i * 45
        box(d, 215, y, 190, 38, f"{h}\n{t}", fill=colors.white, size=7)
    arrow(d, [(150, 60), (190, 60), (190, 169), (215, 169)])
    arrow(d, [(190, 105), (215, 105)])
    box(d, 425, 70, 57, 60, "Submit\n-> Reviewer", fill=colors.HexColor("#E3F3E8"), bold=True, size=7.5)
    arrow(d, [(405, 100), (425, 100)])
    arrow(d, [(405, 169), (415, 169), (415, 118), (425, 118)])
    return d


def d_approvals():
    d = Drawing(W, 150)
    title(d, "How many approvals are needed", 135)
    box(d, 0, 50, 110, 44, "Reviewer passes it\non. Currency and\ntotal are checked", bold=False)
    arrow(d, [(110, 72), (150, 72)])
    box(d, 150, 40, 110, 64, "Currency is USD\nand total is\n5,000 or more?", fill=colors.HexColor("#FFF4D6"), stroke=AMBER, bold=True)
    arrow(d, [(260, 88), (300, 106), (330, 106)], color=GREEN)
    label(d, 290, 112, "yes", color=GREEN, bold=True)
    box(d, 330, 90, 152, 32, "3 approvals\n(third by a senior approver)", fill=LIGHT, size=7.5)
    arrow(d, [(260, 56), (300, 38), (330, 38)])
    label(d, 290, 22, "no", bold=True)
    box(d, 330, 22, 152, 32, "2 approvals", fill=LIGHT, size=7.5)
    return d


def d_rejection():
    d = Drawing(W, 200)
    title(d, "Recall, rejection and correction", 186)
    box(d, 0, 125, 90, 38, "Submitted\n(in review)", bold=True)
    box(d, 130, 125, 100, 38, "Approval has\nstarted?", fill=colors.HexColor("#FFF4D6"), stroke=AMBER, bold=True)
    arrow(d, [(90, 144), (130, 144)])
    box(d, 270, 138, 100, 38, "NO: Recall\nfrom the requisition", fill=colors.HexColor("#E3F3E8"), stroke=GREEN)
    arrow(d, [(230, 150), (270, 154)], color=GREEN)
    box(d, 270, 85, 100, 38, "YES: wait for the\napprovers' decision", fill=LIGHT)
    arrow(d, [(230, 138), (250, 104), (270, 104)])
    box(d, 400, 138, 82, 38, "Edit and\nresubmit", fill=colors.HexColor("#E3F3E8"), stroke=GREEN, bold=True)
    arrow(d, [(370, 157), (400, 157)], color=GREEN)
    box(d, 270, 20, 100, 40, "REJECTED\nreason recorded", fill=colors.HexColor("#FBE3E5"), stroke=DANGER, color=DANGER, bold=True)
    arrow(d, [(320, 85), (320, 60)], color=DANGER)
    label(d, 314, 76, "reviewer or approver\nrejects", anchor="end", color=DANGER, size=6.5)
    box(d, 400, 60, 82, 40, "Correct Mistakes\n(edit, resubmit)", fill=colors.HexColor("#E3F3E8"), stroke=GREEN, size=7.5, bold=True)
    box(d, 400, 8, 82, 40, "Delete\n(permanent)", fill=colors.HexColor("#FBE3E5"), stroke=DANGER, color=DANGER, size=7.5, bold=True)
    arrow(d, [(370, 44), (385, 44), (385, 80), (400, 80)], color=GREEN)
    arrow(d, [(370, 36), (400, 28)], color=DANGER)
    arrow(d, [(441, 100), (441, 138)], color=GREEN, dash=[3, 2])
    label(d, 0, 60, "Both options stay visible to the initiator\nuntil the requisition is resubmitted\nor deleted.", anchor="start", size=7)
    return d


def d_paid():
    d = Drawing(W, 230)
    title(d, "Paid and Not Paid", 216)
    box(d, 0, 140, 120, 46, "Approved\nNOT PAID (red)", fill=colors.HexColor("#FBE3E5"), stroke=DANGER, color=DANGER, bold=True)
    box(d, 190, 140, 120, 46, "PAID (green)", fill=colors.HexColor("#E3F3E8"), stroke=GREEN, color=GREEN, bold=True)
    arrow(d, [(120, 170), (190, 170)], color=GREEN)
    label(d, 155, 188, "initiator:\nMark as Paid", size=6.5)
    label(d, 258, 122, "No undo button.", anchor="start", size=7.5, color=RED, bold=True)
    box(d, 190, 56, 120, 44, "Payment bounced:\nrequest reversal\n(reason + document)", fill=colors.HexColor("#FFF4D6"), stroke=AMBER, size=7.5)
    arrow(d, [(250, 140), (250, 100)])
    box(d, 372, 56, 110, 44, "ADMINISTRATOR\nreviews on Payment\nreversals page", fill=LIGHT, bold=True, size=7.5)
    arrow(d, [(310, 78), (372, 78)])
    box(d, 372, 140, 110, 46, "Admin marks\nNot Paid\n(reason on record)", fill=colors.HexColor("#FBE3E5"), stroke=DANGER, color=DANGER, size=7.5, bold=True)
    arrow(d, [(427, 100), (427, 140)], color=DANGER)
    arrow(d, [(372, 163), (130 + 0, 163 + 0)][:1] + [(340, 163), (340, 210), (60, 210), (60, 186)], color=DANGER, dash=[3, 2])
    label(d, 200, 202, "back to Not Paid, initiator may mark Paid again once the payment succeeds", size=6.5, color=DANGER)
    return d


def d_document():
    d = Drawing(W, 300)
    title(d, "What every downloaded or printed document contains", 286)
    # page mock
    d.add(Rect(10, 8, 230, 270, fillColor=colors.white, strokeColor=BLACK, strokeWidth=1.2))
    parts = [("Logo, company, requisition number", 252, 18, LIGHT), ("PAID or NOT PAID stamp", 226, 22, colors.HexColor("#FBE3E5")),
             ("Details side by side:\nIn Favor Of | Bank\nBranch | Account No\nCurrency | ITF 263\nDate Created | Date Completed", 160, 60, LIGHT),
             ("Account lines and totals", 128, 26, LIGHT),
             ("Signatures: name, image, date and time\nfor everyone involved", 74, 48, LIGHT),
             ("Document code", 40, 28, LIGHT)]
    for t, y, h, f in parts:
        box(d, 20, y, 148, h, t, fill=f, size=6.5)
    box(d, 176, 40, 56, 56, "QR\ncode", fill=BLACK, color=colors.white, bold=True, size=9)
    # callouts
    notes = [(252, "Same file for PDF download and Print View;\nsupporting documents are attached after it"),
             (190, "PDF, Word, Excel and CSV all carry the stamp,\nthe details grid and the signers"),
             (96, "Signature images appear when the person\nhas uploaded one"),
             (60, "The QR opens the public verification page\n(scan with a phone, or click in the PDF)")]
    for y, t in notes:
        arrow(d, [(262, y), (240, y)], color=GREY, width=0.8)
        label(d, 268, y - 2, t, anchor="start", size=7, color=BLACK)
    return d


def d_verify():
    d = Drawing(W, 150)
    title(d, "Verifying a document", 136)
    box(d, 0, 60, 90, 40, "Scan or click\nthe QR code", bold=True)
    box(d, 120, 60, 110, 40, "Opens /verify/id\nwith the document\ncode in the link", size=7.5)
    box(d, 260, 60, 90, 40, "Does the code\nmatch the record\nnow?", fill=colors.HexColor("#FFF4D6"), stroke=AMBER, bold=True, size=7.5)
    arrow(d, [(90, 80), (120, 80)]); arrow(d, [(230, 80), (260, 80)])
    box(d, 385, 90, 97, 38, "VERIFIED\nstatus, payment, payee,\namount, signers", fill=colors.HexColor("#E3F3E8"), stroke=GREEN, color=GREEN, bold=True, size=7)
    box(d, 385, 20, 97, 38, "NOT VERIFIED\nout of date or altered", fill=colors.HexColor("#FBE3E5"), stroke=DANGER, color=DANGER, bold=True, size=7)
    arrow(d, [(350, 88), (385, 108)], color=GREEN); arrow(d, [(350, 72), (385, 40)], color=DANGER)
    label(d, 368, 104, "yes", color=GREEN, bold=True); label(d, 368, 46, "no", color=DANGER, bold=True)
    return d


def d_adminlists():
    d = Drawing(W, 140)
    title(d, "Maintaining the paying bank and account lists", 126)
    steps = ["Download the\nExcel template", "Fill it in\n(keep codes as text)", "Upload the\n.xlsx file", "Account list only:\nchoose Add or Replace", "Initiators see the\nnew drop-downs"]
    bw, g = 86, 13
    for i, s in enumerate(steps):
        x = i * (bw + g)
        box(d, x, 50, bw, 46, s, fill=colors.HexColor("#E3F3E8") if i == 4 else (colors.HexColor("#FFF4D6") if i == 3 else LIGHT), size=7.5, bold=(i == 3))
        if i:
            arrow(d, [(x - g, 73), (x, 73)])
    label(d, W / 2, 30, "Add skips rows already present. Replace deletes the current list first and asks you to confirm.", size=7.5)
    label(d, W / 2, 18, "Requisitions already created keep the values they were saved with.", size=7.5)
    return d


# ---- IT diagrams

def d_arch():
    d = Drawing(W, 250)
    title(d, "System architecture", 238)
    box(d, 0, 140, 100, 50, "Users\nbrowser or phone", bold=True)
    box(d, 135, 140, 110, 50, "Railway edge\nHTTPS, public domain", fill=colors.HexColor("#E8EEF8"), stroke=BLUE, bold=True, size=7.5)
    box(d, 280, 100, 202, 120, "", fill=colors.HexColor("#FAFAFA"))
    label(d, 381, 207, "Service: Testing (gunicorn, 2 workers)", size=7.5, color=BLACK, bold=True)
    box(d, 292, 150, 85, 40, "Flask routes\nauth, requisition,\nadmin, api", size=7)
    box(d, 385, 150, 85, 40, "Document\ngenerator\nPDF DOCX XLSX CSV", size=7)
    box(d, 292, 108, 85, 34, "Models\n(SQLAlchemy)", size=7)
    box(d, 385, 108, 85, 34, "Static files\nsignatures, CSS", size=7)
    arrow(d, [(100, 165), (135, 165)]); arrow(d, [(245, 165), (280, 165)])
    box(d, 280, 20, 105, 50, "Database\nSQLite (default)\nPostgreSQL (advised)", fill=colors.HexColor("#FFF4D6"), stroke=AMBER, bold=True, size=7.5)
    arrow(d, [(334, 108), (334, 70)])
    box(d, 400, 20, 82, 50, "Gemini API\n(optional\nassistant)", fill=colors.HexColor("#E8EEF8"), stroke=BLUE, size=7.5)
    arrow(d, [(441, 108), (441, 70)], dash=[3, 2])
    box(d, 0, 30, 220, 80, "GitHub repository, main branch\nmerge a pull request =\nRailway builds and deploys", fill=LIGHT, size=7.5)
    arrow(d, [(220, 70), (280, 120)], dash=[3, 2], color=GREY)
    label(d, 250, 78, "deploy", size=6.5)
    return d


def d_modules():
    d = Drawing(W, 200)
    title(d, "Code layout", 186)
    box(d, 150, 140, 182, 34, "run.py  ->  app/__init__.py  (app factory)", fill=colors.HexColor("#FBE3E5"), stroke=RED, bold=True, size=7.5)
    routes = ["routes/auth.py\nlogin, register,\nprofile", "routes/requisition.py\nworkflow, downloads,\nreports, batches, verify", "routes/admin.py\nusers, lists, audit,\nreversals", "routes/api.py\nroutes/assistant.py"]
    for i, t in enumerate(routes):
        x = i * 124
        box(d, x, 80, 112, 44, t, size=6.8)
        arrow(d, [(241, 140), (241, 132), (x + 56, 132), (x + 56, 124)], width=0.9, color=GREY)
    utils = ["utils/document_generator.py", "utils/supporting_docs.py", "utils/batch.py, bank_codes.py", "utils/paying_banks.py\nutils/account_codes.py", "utils/notify.py\nworkflow.py"]
    for i, t in enumerate(utils):
        x = i * 99
        box(d, x, 20, 92, 36, t, fill=colors.HexColor("#E8EEF8"), stroke=BLUE, size=6.3)
    arrow(d, [(241, 80), (241, 66), (241, 56)], width=0.9, color=GREY)
    d.add(Line(46, 66, 445, 66, strokeColor=GREY, strokeWidth=0.9))
    for i in range(5):
        arrow(d, [(i * 99 + 46, 66), (i * 99 + 46, 56)], width=0.9, color=GREY)
    box(d, 380, 140, 102, 34, "models.py\nconfig.py", fill=colors.HexColor("#FFF4D6"), stroke=AMBER, size=7.5, bold=True)
    return d


def d_er():
    d = Drawing(W, 275)
    title(d, "Main tables and how they relate", 262)
    def table(x, y, w, name, cols):
        h = 20 + 9 * len(cols)
        d.add(Rect(x, y, w, h, fillColor=colors.white, strokeColor=BLACK, strokeWidth=1))
        d.add(Rect(x, y + h - 14, w, 14, fillColor=BLACK, strokeColor=BLACK))
        d.add(String(x + w / 2, y + h - 10, name, textAnchor="middle", fontSize=7.5, fillColor=colors.white, fontName="Helvetica-Bold"))
        for i, c in enumerate(cols):
            d.add(String(x + 5, y + h - 24 - 9 * i, c, fontSize=6.5, fillColor=BLACK))
        return h
    table(0, 150, 130, "users", ["email, name, role", "can_initiate / review / approve", "is_senior_approver, is_active", "signature_path"])
    table(180, 130, 140, "requisitions", ["requisition_number, payee, bank", "totals, currency, status", "initiator_id, reviewer_id", "paying bank snapshot", "rejection fields", "payment_status, paid_by, paid_at", "reversal and unpaid reason"])
    table(360, 195, 122, "requisition_items", ["account name, code", "location, department", "details, debit, credit"])
    table(360, 120, 122, "approval_logs", ["level, action, approver", "signature, created_at"])
    table(360, 55, 122, "supporting_documents", ["filename, content_type", "data (binary)"])
    table(360, 0, 122, "batch_items", ["batch_id, requisition_id", "reference, account, code"])
    table(180, 20, 140, "paying_banks", ["bank, account name/no", "currency, is_active"])
    table(0, 55, 130, "account_entries", ["account name, code", "location"])
    table(0, 0, 130, "audit_logs, notifications", ["user, action, details", "message, category"])
    for ty in (222, 150, 85, 25):
        arrow(d, [(320, 175), (340, 175), (340, ty), (360, ty)], width=0.9, color=GREY)
    arrow(d, [(180, 190), (130, 190)], width=0.9, color=GREY)
    label(d, 155, 196, "initiator", size=6)
    return d


def d_docflow():
    d = Drawing(W, 130)
    title(d, "What happens on Download or Print", 116)
    steps = ["Browser asks for\n/download/id/pdf\nor /print/id", "Load requisition,\nitems, approval\nlogs, signers", "Generator builds\nPDF, DOCX, XLSX\nor CSV with stamp,\ngrid, QR", "PDF only: merge\nsupporting\ndocuments", "File returned\n(download or\nopened inline)"]
    bw, g = 86, 13
    for i, s in enumerate(steps):
        x = i * (bw + g)
        box(d, x, 30, bw, 56, s, size=7, fill=colors.HexColor("#E3F3E8") if i == 4 else LIGHT)
        if i:
            arrow(d, [(x - g, 58), (x, 58)])
    return d


def d_pipeline():
    d = Drawing(W, 120)
    title(d, "Release pipeline", 106)
    steps = ["Branch and\nchange code", "Open pull\nrequest", "Smoke test\nlocally", "Merge to\nmain", "Railway builds\nand deploys", "Check logs,\nopen the site"]
    bw, g = 68, 14.8
    for i, s in enumerate(steps):
        x = i * (bw + g)
        box(d, x, 30, bw, 46, s, size=7.5, fill=colors.HexColor("#E3F3E8") if i == 5 else (colors.HexColor("#FFF4D6") if i == 3 else LIGHT), bold=(i == 3))
        if i:
            arrow(d, [(x - g, 53), (x, 53)])
    label(d, mid(3 * (bw + g), bw), 18, "merging is the deploy", size=7, color=RED, bold=True)
    return d


def d_persist():
    d = Drawing(W, 190)
    title(d, "Where data lives: today and recommended", 176)
    box(d, 0, 20, 225, 135, "", fill=colors.HexColor("#FDF1F2"), stroke=DANGER)
    label(d, 112, 140, "TODAY: no DATABASE_URL", size=8, color=DANGER, bold=True)
    box(d, 15, 80, 195, 40, "Service container\nSQLite file + signature files\non the container disk", size=7.5)
    box(d, 15, 30, 195, 34, "Every deploy replaces the disk:\nusers, requisitions, lists, signatures lost", fill=colors.HexColor("#FBE3E5"), stroke=DANGER, color=DANGER, size=7.5, bold=True)
    arrow(d, [(112, 80), (112, 64)], color=DANGER)
    box(d, 257, 20, 225, 135, "", fill=colors.HexColor("#EDF7F0"), stroke=GREEN)
    label(d, 370, 140, "RECOMMENDED", size=8, color=GREEN, bold=True)
    box(d, 272, 90, 90, 36, "Service\nTesting", size=7.5)
    box(d, 377, 90, 90, 36, "Railway Postgres\nDATABASE_URL =\n${{Postgres.DATABASE_URL}}", fill=colors.HexColor("#FFF4D6"), stroke=AMBER, size=6.5)
    arrow(d, [(362, 108), (377, 108)], color=GREEN)
    box(d, 272, 30, 195, 40, "Volume mounted at app/static/signatures\n(or signatures stored in the database)", fill=colors.HexColor("#E3F3E8"), stroke=GREEN, size=7)
    arrow(d, [(317, 90), (317, 70)], color=GREEN)
    return d


USER_DIAGRAMS = {
    "1. What the system does": [d_lifecycle],
    "3. Getting started": [d_register],
    "4. Raising a requisition": [d_form],
    "6. Approving": [d_approvals],
    "7. When a requisition is rejected": [d_rejection],
    "8. Paid and Not Paid": [d_paid],
    "9. Downloading and printing": [d_document],
    "Verifying a document": [d_verify],
    "11. Administrator tasks": [d_adminlists],
}
IT_DIAGRAMS = {
    "1. Overview": [d_arch],
    "2. Repository layout": [d_modules],
    "6. Data model": [d_er],
    "7. Key behaviours": [d_docflow],
    "8. Deployment on Railway": [d_pipeline],
    "Persistence: read this before going live": [d_persist],
}

# --------------------------------------------------------------------- styles

ss = getSampleStyleSheet()
BODY = ParagraphStyle("Body", parent=ss["Normal"], fontName="Helvetica", fontSize=9.5, leading=13.5, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=15, textColor=RED, spaceBefore=14, spaceAfter=8, keepWithNext=1)
H3 = ParagraphStyle("H3", parent=ss["Heading3"], fontName="Helvetica-Bold", fontSize=11.5, textColor=BLACK, spaceBefore=10, spaceAfter=5, keepWithNext=1)
BUL = ParagraphStyle("Bul", parent=BODY, leftIndent=16, bulletIndent=5, spaceAfter=3)
CELL = ParagraphStyle("Cell", parent=BODY, fontSize=8.5, leading=11, spaceAfter=0)
CELLH = ParagraphStyle("CellH", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)
CODE = ParagraphStyle("Code", fontName="Courier", fontSize=8, leading=10.5, textColor=BLACK)


def inline(t: str) -> str:
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`([^`]+)`", r'<font face="Courier" size="8.5">\1</font>', t)
    return t


def md_table(rows):
    data = [[Paragraph(inline(c), CELLH if i == 0 else CELL) for c in r] for i, r in enumerate(rows)]
    n = len(rows[0])
    lens = [max(min(len(re.sub(r"[*`]", "", r[j])), 60) for r in rows) + 6 for j in range(n)]
    tot = sum(lens)
    widths = [W * l / tot for l in lens]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLACK), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


class Doc(BaseDocTemplate):
    def __init__(self, path, doc_title, **kw):
        super().__init__(path, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2.2 * cm, bottomMargin=2 * cm, title=doc_title, author="First Mutual Life", **kw)
        self.doc_title = doc_title
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
        self.addPageTemplates([PageTemplate(id="cover", frames=[frame], onPage=self._cover),
                               PageTemplate(id="body", frames=[frame], onPage=self._page)])

    def _cover(self, c, d):
        c.saveState()
        c.setFillColor(BLACK); c.rect(0, A4[1] - 9 * cm, A4[0], 9 * cm, fill=1, stroke=0)
        c.setFillColor(RED); c.rect(0, A4[1] - 9.3 * cm, A4[0], 0.3 * cm, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica", 12)
        c.drawString(2 * cm, A4[1] - 3 * cm, "FIRST MUTUAL LIFE ASSURANCE COMPANY")
        c.setFont("Helvetica-Bold", 30)
        c.drawString(2 * cm, A4[1] - 5.2 * cm, "Requisition System")
        c.setFont("Helvetica", 20)
        c.drawString(2 * cm, A4[1] - 6.8 * cm, self.doc_title)
        c.setFillColor(GREY); c.setFont("Helvetica", 10)
        c.drawString(2 * cm, 2 * cm, "Version 1.0  |  October 2026")
        c.restoreState()

    def _page(self, c, d):
        c.saveState()
        c.setStrokeColor(RED); c.setLineWidth(1.5); c.line(2 * cm, A4[1] - 1.6 * cm, A4[0] - 2 * cm, A4[1] - 1.6 * cm)
        c.setFont("Helvetica", 8); c.setFillColor(GREY)
        c.drawString(2 * cm, A4[1] - 1.4 * cm, "FML Requisition System: " + self.doc_title)
        c.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {d.page}")
        c.restoreState()

    def afterFlowable(self, f):
        if isinstance(f, Paragraph) and f.style.name in ("H2", "H3"):
            key = f"h{abs(hash(f.getPlainText())) % 10**8}"
            self.canv.bookmarkPage(key)
            self.notify("TOCEntry", (0 if f.style.name == "H2" else 1, f.getPlainText(), self.page, key))


def build(md_name, pdf_name, doc_title, diagrams):
    from reportlab.platypus import NextPageTemplate
    lines = open(os.path.join(HERE, md_name), encoding="utf-8").read().split("\n")
    story = [NextPageTemplate("body"), PageBreak()]
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle("t0", fontName="Helvetica-Bold", fontSize=10.5, leading=16, leftIndent=0),
                       ParagraphStyle("t1", fontName="Helvetica", fontSize=9, leading=13, leftIndent=16, textColor=GREY)]
    story += [Paragraph("Contents", ParagraphStyle("TOCH", parent=H2)), toc, PageBreak()]
    i, para, started = 1, [], False

    def flush():
        nonlocal para
        if para:
            story.append(Paragraph(inline(" ".join(para)), BODY))
            para = []

    def add_diagrams(head):
        for key, funcs in diagrams.items():
            if head.startswith(key):
                head_p = story.pop()
                for fn in funcs:
                    story.append(KeepTogether([head_p, Spacer(1, 4), fn()])); story.append(Spacer(1, 8))

    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            flush(); j = i + 1; block = []
            while not lines[j].startswith("```"):
                block.append(lines[j]); j += 1
            if not (block and block[0].startswith("Initiator")):
                story.append(Preformatted("\n".join(block), CODE, dedent=0))
                story.append(Spacer(1, 6))
            i = j + 1; continue
        if ln.startswith("## "):
            flush(); started = True
            if len(story) > 4 and not isinstance(story[-1], PageBreak) and ln[3:].strip().split(".")[0] in ("5", "9", "11") and False:
                story.append(PageBreak())
            h = ln[3:].strip(); story.append(Paragraph(inline(h), H2)); add_diagrams(h); i += 1; continue
        if ln.startswith("### "):
            flush(); h = ln[4:].strip(); story.append(Paragraph(inline(h), H3)); add_diagrams(h); i += 1; continue
        if ln.startswith("|"):
            flush(); rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            story.append(md_table(rows)); story.append(Spacer(1, 8)); continue
        m = re.match(r"^(\s*)(- |\d+\. )(.*)", ln)
        if m:
            flush(); items = []
            while i < len(lines) and re.match(r"^(\s*)(- |\d+\. )(.*)", lines[i]):
                mm = re.match(r"^(\s*)(- |\d+\. )(.*)", lines[i])
                items.append((mm.group(2).strip(), mm.group(3), len(mm.group(1)))); i += 1
            for b, t, ind in items:
                st = ParagraphStyle("b", parent=BUL, leftIndent=16 + ind * 6, bulletIndent=5 + ind * 6)
                story.append(Paragraph(inline(t), st, bulletText="\u2022" if b == "-" else b))
            story.append(Spacer(1, 4)); continue
        if not ln.strip():
            flush(); i += 1; continue
        para.append(ln.strip()); i += 1
    flush()
    doc = Doc(os.path.join(HERE, pdf_name), doc_title)
    doc.multiBuild(story)
    print("wrote", pdf_name)


if __name__ == "__main__":
    build("USER_MANUAL.md", "FML_Requisition_User_Manual.pdf", "User Manual", USER_DIAGRAMS)
    build("IT_GUIDE.md", "FML_Requisition_IT_Guide.pdf", "IT Guide", IT_DIAGRAMS)
