import io
from datetime import datetime
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and print total page numbers: Page X of Y"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(HexColor("#64748b"))
        footer_text = f"Page {self._pageNumber} of {page_count}  •  Apex Attendance ERP V2.0  •  Confidential Official Document"
        self.drawRightString(11 * inch - 0.5 * inch, 0.4 * inch, footer_text)
        self.restoreState()

def generate_attendance_pdf(records, institution_name: str = "Apex Institute of Technology", filter_summary: str = "All Records") -> io.BytesIO:
    """
    Generates a publication-grade Landscape PDF attendance report with summary stats and table.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.6 * inch
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        textColor=HexColor('#1e3a8a'),
        spaceAfter=3
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=HexColor('#475569'),
        spaceAfter=10
    )
    cell_style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10
    )
    cell_bold = ParagraphStyle(
        'CellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10
    )

    story = []

    # Title Banner
    story.append(Paragraph(institution_name.upper(), title_style))
    meta_info = f"OFFICIAL ATTENDANCE REPORT &bull; Filters: {filter_summary} &bull; Generated on: {datetime.now().strftime('%d %b %Y at %I:%M %p')}"
    story.append(Paragraph(meta_info, subtitle_style))

    # Summary Metrics
    total = len(records)
    present = sum(1 for r in records if r.status in ('Present', 'Late', 'Half Day'))
    absent = sum(1 for r in records if r.status == 'Absent')
    rate = round((present / total * 100), 1) if total > 0 else 0.0

    summary_data = [
        [
            Paragraph(f"<b>Total Sessions:</b> {total}", cell_style),
            Paragraph(f"<b>Present Count:</b> {present}", cell_style),
            Paragraph(f"<b>Absent Count:</b> {absent}", cell_style),
            Paragraph(f"<b>Attendance Rate:</b> <font color='#16a34a'><b>{rate}%</b></font>", cell_style),
        ]
    ]
    summary_table = Table(summary_data, colWidths=[2.5*inch, 2.5*inch, 2.5*inch, 2.5*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor('#f1f5f9')),
        ('BOX', (0, 0), (-1, -1), 1, HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 12))

    # Table of Records
    table_headers = [
        "S.No", "Student ID", "Full Name", "Dept",
        "Date", "Time In", "Time Out", "Status", "Method", "Marked By"
    ]
    table_data = [[Paragraph(f"<b>{h}</b>", ParagraphStyle('TH', parent=cell_style, fontName='Helvetica-Bold', textColor=HexColor('#ffffff'))) for h in table_headers]]

    for idx, r in enumerate(records, 1):
        s = r.student
        dept = s.department.code if (s and s.department) else "GEN"
        d_str = r.date.strftime('%d/%m/%Y') if r.date else ""
        in_str = r.time_in.strftime('%I:%M %p') if r.time_in else "-"
        out_str = r.time_out.strftime('%I:%M %p') if r.time_out else "-"
        status_color = '#15803d' if r.status == 'Present' else ('#b91c1c' if r.status == 'Absent' else '#b45309')
        status_p = Paragraph(f"<font color='{status_color}'><b>{r.status}</b></font>", cell_style)
        marker_name = r.marker.username if r.marker else "System"

        row = [
            Paragraph(str(idx), cell_style),
            Paragraph(s.student_id if s else "-", cell_bold),
            Paragraph(s.full_name if s else "-", cell_style),
            Paragraph(dept, cell_style),
            Paragraph(d_str, cell_style),
            Paragraph(in_str, cell_style),
            Paragraph(out_str, cell_style),
            status_p,
            Paragraph(r.method, cell_style),
            Paragraph(marker_name, cell_style)
        ]
        table_data.append(row)

    col_widths = [0.5*inch, 1.1*inch, 1.8*inch, 0.8*inch, 1.0*inch, 1.0*inch, 1.0*inch, 0.9*inch, 0.8*inch, 1.1*inch]
    report_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    table_style = [
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1e3a8a')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e2e8f0')),
    ]

    # Zebra striping
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            table_style.append(('BACKGROUND', (0, i), (-1, i), HexColor('#f8fafc')))

    report_table.setStyle(TableStyle(table_style))
    story.append(report_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer
