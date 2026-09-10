from datetime import date, datetime
from flask import jsonify, request
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func
from app.api import api_bp
from app.extensions import csrf, db
from app.models.user import User
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.department import Department
from app.models.attendance import Attendance
from app.attendance.services import process_qr_attendance
from app.utils.timezone import get_current_ist_date

# Exempt API blueprint from form CSRF so mobile apps and fetch() can easily post
csrf.exempt(api_bp)

@api_bp.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'system': 'QR Attendance ERP V2.0',
        'timestamp': datetime.utcnow().isoformat()
    })

@api_bp.route('/auth/login', methods=['POST'])
def api_login():
    """
    POST /api/auth/login
    Accepts JSON: {"identity": "...", "password": "..."} or form data.
    """
    data = request.get_json(silent=True) or request.form
    identity = (data.get('identity') or data.get('username') or '').strip()
    password = data.get('password') or ''

    if not identity or not password:
        return jsonify({
            'success': False,
            'message': 'Identity and password are required.'
        }), 400

    user = User.query.filter(
        (func.lower(User.username) == func.lower(identity)) |
        (func.lower(User.email) == func.lower(identity))
    ).first()

    if not user:
        student_match = Student.query.filter(
            (func.lower(Student.student_id) == func.lower(identity)) |
            (func.lower(Student.roll_number) == func.lower(identity))
        ).first()
        if student_match and student_match.user:
            user = student_match.user

    if not user or not user.check_password(password):
        return jsonify({
            'success': False,
            'message': 'Invalid credentials. Please verify your username/email and password.'
        }), 401

    if not user.is_active:
        return jsonify({
            'success': False,
            'message': 'Your account has been deactivated. Please contact the administrator.'
        }), 403

    login_user(user, remember=True)

    user_payload = {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': user.role,
        'display_name': user.get_display_name()
    }
    if user.is_student:
        stu = user.student
        if stu:
            user_payload['student'] = stu.to_dict()
        else:
            user_payload['student'] = None
            user_payload['student_unlinked'] = True

    return jsonify({
        'success': True,
        'message': f'Welcome back, {user.get_display_name()}!',
        'user': user_payload
    }), 200

@api_bp.route('/student/me')
@api_bp.route('/student/profile')
@login_required
def get_current_student():
    """
    GET /api/student/me or GET /api/student/profile
    Returns the authenticated student's profile, QR token, and attendance stats.
    """
    if not current_user.is_student:
        return jsonify({
            'success': False,
            'message': 'Unauthorized: Only students can access their personal profile.'
        }), 403

    student = current_user.student
    if not student:
        return jsonify({
            'success': False,
            'error_code': 'PROFILE_NOT_LINKED',
            'message': 'Student profile is not linked to this account. Please contact the administrator.'
        }), 404

    data = student.to_dict()
    data['stats'] = student.calculate_attendance_stats()
    return jsonify({
        'success': True,
        'student': data
    })

@api_bp.route('/auth/logout', methods=['POST', 'GET'])
def api_logout():
    logout_user()
    return jsonify({
        'success': True,
        'message': 'Logged out successfully.'
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
    subject_id = None
    semester = None
    if request.is_json:
        data = request.get_json() or {}
        token = data.get('token')
        subject_id = data.get('subject_id')
        semester = data.get('semester')
    else:
        token = request.form.get('token')
        subject_id = request.form.get('subject_id')
        semester = request.form.get('semester')

    if not token:
        return jsonify({
            'success': False,
            'message': 'QR token missing from request.'
        }), 400

    if subject_id:
        try:
            subject_id = int(subject_id)
        except (ValueError, TypeError):
            subject_id = None

    result = process_qr_attendance(token, marker_user=current_user, subject_id=subject_id, semester=semester)
    if result.get('success'):
        status_code = 200
    elif result.get('error_code') in ('UNAUTHORIZED_SUBJECT', 'UNAUTHORIZED_TEACHER'):
        status_code = 403
    elif result.get('action') in ('ALREADY_COMPLETED', 'COOLDOWN'):
        # Informative status, not a server error
        status_code = 200
    else:
        status_code = 400

    return jsonify(result), status_code

@api_bp.route('/attendance/today')
@login_required
def today_attendance():
    """
    GET /api/attendance/today
    Returns today's recorded attendance list joined with Student.
    """
    today = get_current_ist_date()
    dept_id = request.args.get('dept', type=int)

    query = Attendance.query.join(Student).filter(Attendance.date == today)
    if dept_id:
        query = query.filter(Student.department_id == dept_id)

    records = query.order_by(Attendance.updated_at.desc()).limit(100).all()

    # Build unique present students list for "Present Today" section
    present_students = []
    seen_ids = set()
    for r in records:
        if r.student and r.status in ('Present', 'Late', 'Half Day') and r.student.id not in seen_ids:
            seen_ids.add(r.student.id)
            present_students.append({
                'id': r.student.id,
                'student_id': r.student.student_id,
                'full_name': r.student.full_name,
                'roll_number': r.student.roll_number,
                'department': r.student.department.name if r.student.department else None,
                'course': r.student.course,
                'time_in': r.time_in.strftime('%I:%M %p') if r.time_in else '-'
            })

    return jsonify({
        'success': True,
        'date': today.strftime('%Y-%m-%d'),
        'count': len(records),
        'present_count': len(present_students),
        'present_students': present_students,
        'records': [r.to_dict() for r in records]
    })

@api_bp.route('/dashboard/stats')
@login_required
def dashboard_stats():
    """
    GET /api/dashboard/stats
    Returns realtime KPI counters and present students roster.
    """
    today = get_current_ist_date()
    total_students = Student.query.filter_by(is_active=True).count()
    total_teachers = Teacher.query.filter_by(is_active=True).count()

    present_today = Attendance.query.filter(
        Attendance.date == today,
        Attendance.status.in_(['Present', 'Late', 'Half Day'])
    ).count()

    absent_today = max(0, total_students - present_today)
    rate = round((present_today / total_students * 100), 1) if total_students > 0 else 0.0

    present_records = (
        Attendance.query
        .join(Student)
        .filter(
            Attendance.date == today,
            Attendance.status.in_(['Present', 'Late', 'Half Day'])
        )
        .order_by(Attendance.time_in.asc().nullslast())
        .all()
    )
    present_students = [
        {
            'student_id': r.student.student_id,
            'full_name': r.student.full_name,
            'roll_number': r.student.roll_number,
            'department': r.student.department.name if r.student.department else None,
            'course': r.student.course,
            'time_in': r.time_in.strftime('%I:%M %p') if r.time_in else '-'
        }
        for r in present_records if r.student
    ]

    return jsonify({
        'success': True,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'present_today': present_today,
        'absent_today': absent_today,
        'attendance_rate': rate,
        'present_students': present_students
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

@api_bp.route('/subjects')
@login_required
def list_subjects():
    """
    GET /api/subjects
    Returns list of active subjects.
    Optional query params: dept, semester, q
    """
    from app.models.subject import Subject
    query = Subject.query.filter_by(is_active=True)
    dept_id = request.args.get('dept', type=int)
    semester = request.args.get('semester', '').strip()
    search = request.args.get('q', '').strip()

    if dept_id:
        query = query.filter_by(department_id=dept_id)
    if semester:
        query = query.filter_by(semester=semester)
    if search:
        query = query.filter(
            (Subject.subject_name.ilike(f"%{search}%")) |
            (Subject.subject_code.ilike(f"%{search}%"))
        )

    subjects = query.order_by(Subject.subject_code).all()
    return jsonify({
        'success': True,
        'count': len(subjects),
        'subjects': [s.to_dict() for s in subjects]
    })

@api_bp.route('/teacher/subjects')
@login_required
def teacher_subjects():
    """
    GET /api/teacher/subjects
    Returns subjects assigned to the authenticated teacher with semester, teacher name, and class context.
    """
    from app.models.subject import Subject
    from app.models.subject_assignment import TeacherSubjectAssignment

    subject_list = []
    if current_user.is_teacher:
        teacher = current_user.teacher_profile
        if not teacher:
            return jsonify({'success': False, 'message': 'Teacher profile not linked.'}), 404
        
        assignments = teacher.get_active_assignments()
        for asgn in assignments:
            s = asgn.subject
            if not s or not s.is_active:
                continue
            subject_list.append({
                'id': s.id,
                'assignment_id': asgn.id,
                'subject_id': s.id,
                'name': s.subject_name,
                'subject_name': s.subject_name,
                'code': s.subject_code,
                'subject_code': s.subject_code,
                'teacher_name': teacher.full_name,
                'semester': asgn.semester or (s.semester or ''),
                'department': asgn.department.name if asgn.department else (s.department.name if s.department else ''),
                'course': asgn.course or (s.course or ''),
                'section': asgn.section or ''
            })
    elif current_user.is_admin:
        assignments = TeacherSubjectAssignment.query.filter_by(is_active=True).all()
        if assignments:
            for asgn in assignments:
                s = asgn.subject
                if not s or not s.is_active:
                    continue
                subject_list.append({
                    'id': s.id,
                    'assignment_id': asgn.id,
                    'subject_id': s.id,
                    'name': s.subject_name,
                    'subject_name': s.subject_name,
                    'code': s.subject_code,
                    'subject_code': s.subject_code,
                    'teacher_name': asgn.teacher.full_name if asgn.teacher else 'Admin',
                    'semester': asgn.semester or (s.semester or ''),
                    'department': asgn.department.name if asgn.department else (s.department.name if s.department else ''),
                    'course': asgn.course or (s.course or ''),
                    'section': asgn.section or ''
                })
        else:
            subjects = Subject.query.filter_by(is_active=True).order_by(Subject.subject_code).all()
            for s in subjects:
                subject_list.append({
                    'id': s.id,
                    'assignment_id': None,
                    'subject_id': s.id,
                    'name': s.subject_name,
                    'subject_name': s.subject_name,
                    'code': s.subject_code,
                    'subject_code': s.subject_code,
                    'teacher_name': 'Administrator',
                    'semester': s.semester or '',
                    'department': s.department.name if s.department else '',
                    'course': s.course or '',
                    'section': ''
                })
    else:
        return jsonify({'success': False, 'message': 'Unauthorized: Only faculty can access assigned subjects.'}), 403

    return jsonify({
        'success': True,
        'count': len(subject_list),
        'subjects': subject_list
    })

@api_bp.route('/student/attendance')
@login_required
def student_attendance_summary():
    """
    GET /api/student/attendance
    Returns authenticated student's overall & subject-wise attendance statistics.
    """
    if not current_user.is_student:
        return jsonify({'success': False, 'message': 'Unauthorized: Only students can access this endpoint.'}), 403

    student = current_user.student
    if not student:
        return jsonify({'success': False, 'message': 'Student profile not linked.'}), 404

    overall_stats = student.calculate_attendance_stats()
    subject_wise = student.get_subject_wise_attendance()

    return jsonify({
        'success': True,
        'student_id': student.student_id,
        'student_name': student.full_name,
        'overall_stats': overall_stats,
        'subject_wise': subject_wise
    })

@api_bp.route('/student/attendance/<int:subject_id>')
@login_required
def student_subject_attendance_detail(subject_id):
    """
    GET /api/student/attendance/<subject_id>
    Returns detailed logs for the authenticated student for the given subject.
    """
    if not current_user.is_student:
        return jsonify({'success': False, 'message': 'Unauthorized: Only students can access this endpoint.'}), 403

    student = current_user.student
    if not student:
        return jsonify({'success': False, 'message': 'Student profile not linked.'}), 404

    from app.models.subject import Subject
    subject = Subject.query.get_or_404(subject_id)

    records = student.attendances.filter_by(subject_id=subject_id).order_by(Attendance.date.desc()).all()
    total_classes = len(records)
    present_classes = sum(1 for a in records if a.status in ('Present', 'Late', 'Half Day'))
    absent_classes = sum(1 for a in records if a.status == 'Absent')
    pct = round((present_classes / total_classes * 100), 1) if total_classes > 0 else 0.0

    return jsonify({
        'success': True,
        'subject': subject.to_dict(),
        'stats': {
            'total_classes': total_classes,
            'present_classes': present_classes,
            'absent_classes': absent_classes,
            'attendance_percentage': pct
        },
        'records': [r.to_dict() for r in records]
    })
