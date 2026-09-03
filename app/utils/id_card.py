import io
import os
from pathlib import Path
from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from app.utils.qr_generator import generate_qr_bytes

# Standard CR80 ID Card dimensions: 3.375 x 2.125 inches
CARD_WIDTH = 3.375 * inch
CARD_HEIGHT = 2.125 * inch

def generate_student_id_card_pdf(student, institution_name: str = "Dr. Virendra Swarup Memorial Trust Group of Institutions") -> io.BytesIO:
    """
    Generates a high-resolution, vector-crisp PDF ID card formatted to standard CR80 physical card dimensions.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(CARD_WIDTH, CARD_HEIGHT))

    # Color definitions
    primary_color = HexColor("#1e3a8a") # Deep Navy
    accent_color = HexColor("#3b82f6")  # Electric Blue
    dark_text = HexColor("#0f172a")
    sub_text = HexColor("#475569")
    bg_card = HexColor("#f8fafc")

    # Background
    c.setFillColor(bg_card)
    c.rect(0, 0, CARD_WIDTH, CARD_HEIGHT, fill=True, stroke=False)

    # Top Header Banner
    c.setFillColor(primary_color)
    c.rect(0, CARD_HEIGHT - 40, CARD_WIDTH, 40, fill=True, stroke=False)

    # Institution Name in Header
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 7.5)
    c.drawCentredString(CARD_WIDTH / 2.0, CARD_HEIGHT - 11, "DR. VIRENDRA SWARUP MEMORIAL TRUST")
    c.setFillColor(HexColor("#fde047"))
    c.setFont("Helvetica-Bold", 7.0)
    c.drawCentredString(CARD_WIDTH / 2.0, CARD_HEIGHT - 19, "GROUP OF INSTITUTIONS")
    c.setFillColor(HexColor("#e2e8f0"))
    c.setFont("Helvetica", 4.2)
    c.drawCentredString(CARD_WIDTH / 2.0, CARD_HEIGHT - 27, "Banthar, Charlestown Institutional Area, Kanpur-Lucknow National Highway, Unnao, UP – 209801")
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 5.2)
    c.drawCentredString(CARD_WIDTH / 2.0, CARD_HEIGHT - 35, "OFFICIAL STUDENT IDENTITY CARD")

    # Accent divider stripe
    c.setFillColor(accent_color)
    c.rect(0, CARD_HEIGHT - 42, CARD_WIDTH, 2, fill=True, stroke=False)

    # Photo Box on Left
    photo_x = 12
    photo_y = 28
    photo_w = 54
    photo_h = 68

    photo_rendered = False
    if student.photo:
        photo_path = Path("app/static/uploads") / student.photo
        if photo_path.exists():
            try:
                c.drawImage(str(photo_path), photo_x, photo_y, width=photo_w, height=photo_h, preserveAspectRatio=True, anchor='c')
                photo_rendered = True
            except Exception:
                photo_rendered = False

    if not photo_rendered:
        # Placeholder avatar box
        c.setFillColor(HexColor("#e2e8f0"))
        c.roundRect(photo_x, photo_y, photo_w, photo_h, 4, fill=True, stroke=True)
        c.setFillColor(sub_text)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(photo_x + photo_w/2.0, photo_y + photo_h/2.0 - 5, student.full_name[0].upper())

    # Border around photo
    c.setStrokeColor(HexColor("#cbd5e1"))
    c.setLineWidth(1)
    c.roundRect(photo_x, photo_y, photo_w, photo_h, 2, fill=False, stroke=True)

    # Student Details on Middle Column
    detail_x = photo_x + photo_w + 10
    detail_y = CARD_HEIGHT - 50

    # Name
    c.setFillColor(dark_text)
    c.setFont("Helvetica-Bold", 9)
    name_display = student.full_name
    if len(name_display) > 22:
        name_display = name_display[:20] + "..."
    c.drawString(detail_x, detail_y, name_display)

    # ID & Roll
    c.setFont("Helvetica-Bold", 7)
    c.setFillColor(primary_color)
    c.drawString(detail_x, detail_y - 12, f"ID: {student.student_id}")

    c.setFont("Helvetica", 6.5)
    c.setFillColor(sub_text)
    c.drawString(detail_x, detail_y - 22, f"Roll No: {student.roll_number}")

    # Department & Course
    dept_name = student.department.name if student.department else "General"
    if len(dept_name) > 20:
        dept_name = student.department.code if student.department else "General"
    c.drawString(detail_x, detail_y - 32, f"Dept: {dept_name}")
    c.drawString(detail_x, detail_y - 42, f"Sem: {student.semester} ({student.section or 'A'})")
    c.drawString(detail_x, detail_y - 52, f"Valid: 2024-2028")

    # QR Code on Right
    qr_w = 54
    qr_h = 54
    qr_x = CARD_WIDTH - qr_w - 10
    qr_y = 35

    qr_buffer = generate_qr_bytes(student.qr_token, box_size=4, border=1)
    c.drawImage(ImageReader(qr_buffer), qr_x, qr_y, width=qr_w, height=qr_h)

    c.setFillColor(sub_text)
    c.setFont("Helvetica", 5.5)
    c.drawCentredString(qr_x + qr_w/2.0, qr_y - 7, "SCAN FOR ATTENDANCE")

    # Bottom bar
    c.setFillColor(primary_color)
    c.rect(0, 0, CARD_WIDTH, 12, fill=True, stroke=False)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica", 5.5)
    c.drawCentredString(CARD_WIDTH / 2.0, 4, "Property of Institution. If found, please return to Admin Office.")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer
