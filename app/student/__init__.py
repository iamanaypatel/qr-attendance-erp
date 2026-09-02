from flask import Blueprint

student_bp = Blueprint('student', __name__, url_prefix='/student')

from app.student import routes
