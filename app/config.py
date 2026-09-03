import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

def fix_database_url(url: str) -> str:
    if not url:
        return f"sqlite:///{BASE_DIR / 'instance' / 'qr_attendance.db'}"
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default-dev-secret-key-qr-erp-2026')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = fix_database_url(os.environ.get('DATABASE_URL', ''))
    
    # Upload limits: 2MB max file size
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 2 * 1024 * 1024))
    UPLOAD_FOLDER = BASE_DIR / os.environ.get('UPLOAD_FOLDER', 'app/static/uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    
    # Institution defaults
    INSTITUTION_NAME = os.environ.get('INSTITUTION_NAME', 'Dr. Virendra Swarup Memorial Trust Group of Institutions')
    INSTITUTION_EMAIL = os.environ.get('INSTITUTION_EMAIL', 'contact@vsmt.edu.in')
    INSTITUTION_PHONE = os.environ.get('INSTITUTION_PHONE', '+91 512-2580000')
    INSTITUTION_ADDRESS = os.environ.get('INSTITUTION_ADDRESS', 'Dr. Virendra Swarup Memorial Trust Group of Institutions, Kanpur-Lucknow National Highway, Unnao, UP')
    
    # SMTP / Mail
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() in ('true', '1', 't')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@apex-institute.edu')
    
    # WTForms / CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

class TestingConfig(Config):
    DEBUG = False
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key'

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
