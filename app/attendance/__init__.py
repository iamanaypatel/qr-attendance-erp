from flask import Blueprint

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')

from app.attendance import routes
