from datetime import date, datetime
from flask import jsonify, request
from flask_login import current_user, login_required
from app.api import api_bp
from app.extensions import csrf, db
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.department import Department
from app.models.attendance import Attendance
from app.attendance.services import process_qr_attendance

# Exempt API blueprint from form CSRF so JavaScript fetch() can easily post
csrf.exempt(api_bp)

@api_bp.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'system': 'QR Attendance ERP V2.0',
        'timestamp': datetime.utcnow().isoformat()
    })

@api_bp.route('/attendance/scan', methods=['POST'])
@login_required
def scan_attendance():
    """
    POST /api/attendance/scan
    Payload: {"token": "..."} or form-encoded "token"
    """
    if not (current_user.is_admin or current_user.is_teacher):
        return jsonify({
            'success': False,
            'message': 'Unauthorized: Only teachers and administrators can scan attendance.'
        }), 403

    token = None
    if request.is_json:
        data = request.get_json() or {}
        token = data.get('token')
    else:
        token = request.form.get('token')

    if not token:
        return jsonify({
            'success': False,
            'message': 'QR token missing from request.'
        }), 400

    result = process_qr_attendance(token, marker_user=current_user)
    status_code = 200 if result.get('success') else 400
    if result.get('action') in ('ALREADY_COMPLETED', 'COOLDOWN'):
        # Informative status, not a server error
        status_code = 200

    return jsonify(result), status_code

@api_bp.route('/attendance/today')
@login_required
def today_attendance():
    """
    GET /api/attendance/today
    Returns today's recorded attendance list.
    """
    today = date.today()
    dept_id = request.args.get('dept', type=int)

    query = Attendance.query.filter_by(date=today)
    if dept_id:
        query = query.join(Student).filter(Student.department_id == dept_id)

    records = query.order_by(Attendance.updated_at.desc()).limit(50).all()
    return jsonify({
        'success': True,
        'date': today.strftime('%Y-%m-%d'),
        'count': len(records),
        'records': [r.to_dict() for r in records]
    })

@api_bp.route('/dashboard/stats')
@login_required
def dashboard_stats():
    """
    GET /api/dashboard/stats
    Returns realtime KPI counters.
    """
    today = date.today()
    total_students = Student.query.filter_by(is_active=True).count()
    total_teachers = Teacher.query.filter_by(is_active=True).count()

    present_today = Attendance.query.filter(
        Attendance.date == today,
        Attendance.status.in_(['Present', 'Late', 'Half Day'])
    ).count()

    absent_today = max(0, total_students - present_today)
    rate = round((present_today / total_students * 100), 1) if total_students > 0 else 0.0

    return jsonify({
        'success': True,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'present_today': present_today,
        'absent_today': absent_today,
        'attendance_rate': rate
    })

@api_bp.route('/students')
@login_required
def list_students():
    """
    GET /api/students
    """
    query = Student.query.filter_by(is_active=True)
    dept_id = request.args.get('dept', type=int)
    search = request.args.get('q', '').strip()

    if dept_id:
        query = query.filter_by(department_id=dept_id)
    if search:
        search_fmt = f"%{search}%"
        query = query.filter(
            (Student.full_name.ilike(search_fmt)) |
            (Student.student_id.ilike(search_fmt))
        )

    students = query.order_by(Student.full_name).limit(50).all()
    return jsonify({
        'success': True,
        'count': len(students),
        'students': [s.to_dict() for s in students]
    })

@api_bp.route('/students/<int:id>')
@login_required
def get_student(id):
    student = Student.query.get_or_404(id)
    stats = student.calculate_attendance_stats()
    data = student.to_dict()
    data['stats'] = stats
    return jsonify({
        'success': True,
        'student': data
    })
