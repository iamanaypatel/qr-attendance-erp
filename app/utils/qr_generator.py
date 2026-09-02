import io
import base64
import qrcode
from qrcode.image.pil import PilImage

def generate_qr_data_uri(data: str, box_size: int = 10, border: int = 2) -> str:
    """
    Generates a high-contrast QR code as a base64 encoded data URI string
    safe for embedding directly into HTML <img src="data:image/png;base64,...">.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{b64_str}"

def generate_qr_bytes(data: str, box_size: int = 10, border: int = 2) -> io.BytesIO:
    """
    Returns BytesIO object containing PNG bytes for file downloads or ReportLab embedding.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
