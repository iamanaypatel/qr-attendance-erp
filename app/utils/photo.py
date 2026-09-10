import os
import re
import uuid
import logging
from pathlib import Path
from flask import current_app
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
MAX_DIMENSION = 800  # Max width/height in pixels for student profile photos
JPEG_QUALITY = 88   # Optimal balance between high visual fidelity and lightweight size

def get_upload_folder() -> Path:
    """Resolve and ensure the configured upload directory exists."""
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'app/static/uploads')
    if isinstance(upload_folder, str):
        upload_folder = Path(upload_folder)
    if not upload_folder.is_absolute():
        base_dir = Path(current_app.root_path).parent
        upload_folder = base_dir / upload_folder
    upload_folder.mkdir(parents=True, exist_ok=True)
    return upload_folder

def validate_and_save_photo(file_storage, student_id: str, old_photo_filename: str = None) -> tuple[str | None, str | None]:
    """
    Validates, normalizes, and saves a student profile photo safely.

    Parameters:
        file_storage: Werkzeug FileStorage object from request.files or form.photo.data
        student_id: Associated Student ID (e.g. 'STU2026001')
        old_photo_filename: Optional previous photo filename to clean up upon replacement

    Returns:
        tuple (saved_filename, error_message):
            - On success: (filename, None)
            - On failure: (None, human_readable_error)
    """
    if not file_storage or isinstance(file_storage, str):
        return None, "No file provided."

    if not hasattr(file_storage, 'filename') or not file_storage.filename or not file_storage.filename.strip():
        return None, "No file selected."

    original_filename = file_storage.filename.strip()
    if '.' not in original_filename:
        return None, "Unable to upload image. Please select a valid JPG, PNG, or WEBP image."

    ext = original_filename.rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return None, "Unable to upload image. Please select a valid JPG, PNG, or WEBP image."

    # 1. Content validation using Pillow (magic bytes & file integrity)
    try:
        file_storage.stream.seek(0)
        img = Image.open(file_storage.stream)
        img_format = (img.format or '').upper()

        if img_format not in ('JPEG', 'JPG', 'PNG', 'WEBP'):
            return None, "Unable to upload image. The file is not a valid JPG, PNG, or WEBP image."

        # Verify integrity (catches corrupted/truncated byte streams)
        img.verify()

        # Reopen image because verify() invalidates the Pillow image object
        file_storage.stream.seek(0)
        img = Image.open(file_storage.stream)
    except (UnidentifiedImageError, OSError, Exception) as e:
        logger.warning(f"Image validation rejected corrupted or non-image upload '{original_filename}': {e}")
        return None, "Unable to upload image. Please select a valid, uncorrupted JPG, PNG, or WEBP image."

    # 2. Image Normalization
    try:
        # Auto-transpose EXIF orientation (fixes rotated mobile phone camera shots)
        img = ImageOps.exif_transpose(img)

        # Convert palette or transparent formats (RGBA, LA, P) to clean RGB with white background
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img = img.convert('RGBA')
            canvas = Image.new('RGB', img.size, (255, 255, 255))
            canvas.paste(img, mask=img.split()[3])
            img = canvas
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Constrain dimensions proportionally to max 800x800 for crispness without bloat
        if img.width > MAX_DIMENSION or img.height > MAX_DIMENSION:
            img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)

        # 3. Generate safe unique filename
        clean_sid = re.sub(r'[^a-zA-Z0-9_-]', '', str(student_id or 'student'))
        unique_token = uuid.uuid4().hex[:10]
        filename = f"student_{clean_sid}_{unique_token}.jpg"

        upload_folder = get_upload_folder()
        target_path = upload_folder / filename

        # 4. Save normalized, high quality progressive JPEG
        img.save(target_path, 'JPEG', quality=JPEG_QUALITY, optimize=True)

        # 5. Clean up old photo if replaced
        if old_photo_filename and isinstance(old_photo_filename, str):
            old_name = Path(old_photo_filename.strip()).name
            if old_name and old_name != filename:
                old_path = upload_folder / old_name
                if old_path.exists() and old_path.is_file():
                    try:
                        old_path.unlink()
                    except Exception as e:
                        logger.warning(f"Could not delete old photo '{old_name}': {e}")

        return filename, None

    except Exception as e:
        logger.error(f"Error processing and saving student photo: {e}", exc_info=True)
        return None, "An error occurred while saving the image. Please try again."

def delete_student_photo(photo_filename: str) -> bool:
    """Safely remove a photo file from the upload directory."""
    if not photo_filename or not isinstance(photo_filename, str):
        return False
    try:
        upload_folder = get_upload_folder()
        file_path = upload_folder / Path(photo_filename.strip()).name
        if file_path.exists() and file_path.is_file():
            file_path.unlink()
            return True
    except Exception as e:
        logger.warning(f"Error deleting student photo '{photo_filename}': {e}")
    return False

def get_student_photo_path(photo_filename: str) -> Path | None:
    """Resolve the absolute filesystem path for PDF generation or checks."""
    if not photo_filename or not isinstance(photo_filename, str):
        return None
    clean = Path(photo_filename.strip()).name
    upload_folder = get_upload_folder()
    candidate = upload_folder / clean
    if candidate.exists() and candidate.is_file():
        return candidate
    return None

def get_student_photo_url(photo_filename: str, updated_at=None) -> str | None:
    """Generate the static browser URL with a cache-busting timestamp query parameter."""
    if not photo_filename or not isinstance(photo_filename, str):
        return None
    clean = photo_filename.strip()
    if clean.startswith('http://') or clean.startswith('https://'):
        return clean
    if clean.startswith('/static/'):
        clean = clean[len('/static/'):]
    elif clean.startswith('static/'):
        clean = clean[len('static/'):]
    if clean.startswith('uploads/'):
        clean = clean[len('uploads/'):]
    filename_only = Path(clean).name

    v = int(updated_at.timestamp()) if (updated_at and hasattr(updated_at, 'timestamp')) else 1
    return f"/static/uploads/{filename_only}?v={v}"
