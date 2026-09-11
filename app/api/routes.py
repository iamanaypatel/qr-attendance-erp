from datetime import date, datetime
from flask import jsonify, request, current_app
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
    import os
    return jsonify({
        'status': 'healthy',
        'system': 'QR Attendance ERP V2.0',
        'commit': os.environ.get('RENDER_GIT_COMMIT', 'local'),
        'timestamp': datetime.utcnow().isoformat()
    })

@api_bp.route('/diagnostics/db-forensic')
def db_forensic():
    """
    Forensic diagnostics route to inspect the database schema, tables, and test query execution
    directly on the deployed live environment.
    """
    import os
    import traceback
    from sqlalchemy import inspect, text

    results = {
        'commit': os.environ.get('RENDER_GIT_COMMIT', 'local'),
        'env': os.environ.get('FLASK_ENV', 'unknown'),
        'dialect': db.engine.dialect.name,
        'driver': db.engine.url.drivername
    }
    try:
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        results['tables'] = existing_tables

        table_cols = {}
        for t in ['attendances', 'subjects', 'teachers', 'students', 'academic_sessions', 'class_coordinators', 'teacher_subject_assignments', 'holidays', 'users']:
            if t in existing_tables:
                table_cols[t] = [c['name'] for c in inspector.get_columns(t)]
            else:
                table_cols[t] = 'TABLE_MISSING'
        results['table_columns'] = table_cols

        # Test each section query
        test_results = {}
        
        # 1. Dashboard
        try:
            today = get_current_ist_date()
            stu_count = Student.query.count()
            tch_count = Teacher.query.count()
            att_count = Attendance.query.count()
            gen_count = Attendance.query.filter(Attendance.date == today, Attendance.attendance_type == 'GENERAL').count()
            test_results['dashboard'] = {
                'status': 'OK',
                'students': stu_count,
                'teachers': tch_count,
                'total_attendances': att_count,
                'general_today': gen_count
            }
        except Exception as ex:
            test_results['dashboard'] = {'status': 'ERROR', 'error': f"{type(ex).__name__}: {str(ex)}", 'trace': traceback.format_exc()}

        # 2. Calendar / Holiday
        try:
            from app.models.holiday import Holiday
            holidays = Holiday.query.all()
            test_results['calendar'] = {'status': 'OK', 'holidays_count': len(holidays)}
        except Exception as ex:
            test_results['calendar'] = {'status': 'ERROR', 'error': f"{type(ex).__name__}: {str(ex)}", 'trace': traceback.format_exc()}

        # 3. Take Attendance (Scanner)
        try:
            from app.models.subject import Subject
            subs = Subject.query.all()
            test_results['scanner'] = {'status': 'OK', 'subjects_count': len(subs)}
        except Exception as ex:
            test_results['scanner'] = {'status': 'ERROR', 'error': f"{type(ex).__name__}: {str(ex)}", 'trace': traceback.format_exc()}

        # 4. Class Coordinator
        try:
            from app.models.class_coordinator import ClassCoordinator
            coords = ClassCoordinator.query.all()
            test_results['class_coordinators'] = {'status': 'OK', 'count': len(coords)}
        except Exception as ex:
            test_results['class_coordinators'] = {'status': 'ERROR', 'error': f"{type(ex).__name__}: {str(ex)}", 'trace': traceback.format_exc()}

        # 5. Subject Assignments
        try:
            from app.models.subject_assignment import TeacherSubjectAssignment
            asgns = TeacherSubjectAssignment.query.all()
            test_results['subject_assignments'] = {'status': 'OK', 'count': len(asgns)}
        except Exception as ex:
            test_results['subject_assignments'] = {'status': 'ERROR', 'error': f"{type(ex).__name__}: {str(ex)}", 'trace': traceback.format_exc()}

        # 6. Subjects
        try:
            from app.models.subject import Subject
            subs = Subject.query.all()
            rendered_subs = [s.to_dict() for s in subs[:3]]
            test_results['subjects'] = {'status': 'OK', 'sample_count': len(subs), 'sample': rendered_subs}
        except Exception as ex:
            test_results['subjects'] = {'status': 'ERROR', 'error': f"{type(ex).__name__}: {str(ex)}", 'trace': traceback.format_exc()}

        results['tests'] = test_results
        return jsonify({'success': True, 'forensics': results}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': f"{type(e).__name__}: {str(e)}", 'trace': traceback.format_exc()}), 500

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

    token = user.generate_auth_token()

    return jsonify({
        'success': True,
        'message': f'Welcome back, {user.get_display_name()}!',
        'user': user_payload,
        'token': token
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

@api_bp.route('/attendance/scan', methods=['POST'], strict_slashes=False)
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
    attendance_type = 'SUBJECT'
    if request.is_json:
        data = request.get_json() or {}
        token = data.get('token')
        subject_id = data.get('subject_id')
        semester = data.get('semester')
        attendance_type = data.get('attendance_type') or ('GENERAL' if subject_id is None else 'SUBJECT')
    else:
        token = request.form.get('token')
        subject_id = request.form.get('subject_id')
        semester = request.form.get('semester')
        attendance_type = request.form.get('attendance_type') or ('GENERAL' if subject_id is None else 'SUBJECT')

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

    teacher_id = current_user.teacher_profile.id if getattr(current_user, 'teacher_profile', None) else current_user.id
    current_app.logger.info(
        f"API_SCAN_REQUEST: MarkerUser={current_user.id} Teacher={teacher_id} Type={attendance_type} "
        f"SubjectId={subject_id} Semester={semester} TokenPrefix={token[:6] if token else ''}"
    )

    result = process_qr_attendance(
        token,
        marker_user=current_user,
        subject_id=subject_id,
        semester=semester,
        attendance_type=attendance_type
    )
    if 'action' not in result:
        result['action'] = 'SUCCESS' if result.get('success') else (result.get('error_code') or 'SCAN_FAILED')

    if result.get('success'):
        status_code = 200
    elif result.get('error_code') in ('UNAUTHORIZED_SUBJECT', 'UNAUTHORIZED_TEACHER', 'UNAUTHORIZED_COORDINATOR'):
        status_code = 403
    elif result.get('action') in ('ALREADY_COMPLETED', 'COOLDOWN'):
        # Informative status, not a server error
        status_code = 200
    else:
        status_code = 400

    student_id = result.get('student', {}).get('student_id') if result.get('student') else '-'
    current_app.logger.info(
        f"API_SCAN_RESPONSE: Status={status_code} Teacher={teacher_id} Type={result.get('attendance_type', attendance_type)} "
        f"Subject={subject_id} Student={student_id} Action={result.get('action')} Success={result.get('success')}"
    )

    return jsonify(result), status_code

@api_bp.before_request
def authenticate_api_request():
    """
    If an Authorization Bearer token or X-API-Token is provided in the headers,
    authenticate the user for this API request, regardless of cookie state.
    This guarantees that mobile API calls never fail auth or return 302 due to
    stale, truncated, or missing cookies.
    """
    auth_header = request.headers.get('Authorization')
    token = None
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ', 1)[1].strip()
    elif request.headers.get('X-API-Token'):
        token = request.headers.get('X-API-Token').strip()

    if token:
        user = User.verify_auth_token(token)
        if user and user.is_active:
            login_user(user, remember=False)

@api_bp.after_request
def intercept_api_redirects(response):
    """
    Ensure no API endpoint under /api/ ever returns an HTTP 302 or other redirect.
    If an unhandled redirect occurs, convert it to an appropriate JSON response.
    """
    if response.status_code in (301, 302, 303, 307, 308):
        location = response.headers.get('Location', '')
        current_app.logger.warning(
            f"API_REDIRECT_INTERCEPTED: Path={request.path} Method={request.method} Status={response.status_code} Location={location}"
        )
        if 'login' in location.lower():
            return jsonify({
                'success': False,
                'action': 'UNAUTHORIZED',
                'message': 'Authentication session expired or invalid. Please log in again.'
            }), 401
        return jsonify({
            'success': False,
            'action': 'REDIRECT_BLOCKED',
            'location': location,
            'message': f'Redirect blocked for API request: {location}'
        }), 400
    return response

@api_bp.route('/attendance/today')
@login_required
def today_attendance():
    """
    GET /api/attendance/today
    Returns today's recorded attendance list joined with Student.
    """
    today = get_current_ist_date()
    dept_id = request.args.get('dept', type=int)
    att_type = request.args.get('type', '').strip().upper()
    subject_id = request.args.get('subject_id', type=int)

    query = Attendance.query.join(Student).filter(Attendance.date == today)
    if dept_id:
        query = query.filter(Student.department_id == dept_id)
    if att_type:
        query = query.filter(Attendance.attendance_type == att_type)
    if subject_id:
        query = query.filter(Attendance.subject_id == subject_id)

    records = query.order_by(Attendance.updated_at.desc()).limit(100).all()

    # Build unique present entries scoped by attendance context
    present_students = []
    seen_keys = set()
    for r in records:
        if r.student and r.status in ('Present', 'Late', 'Half Day'):
            key = r.student.id if (att_type == 'GENERAL' or r.attendance_type == 'GENERAL') else (r.student.id, r.subject_id)
            if key not in seen_keys:
                seen_keys.add(key)
                present_students.append({
                    'id': r.student.id,
                    'student_id': r.student.student_id,
                    'full_name': r.student.full_name,
                    'roll_number': r.student.roll_number,
                    'department': r.student.department.name if r.student.department else None,
                    'course': r.student.course,
                    'attendance_type': r.attendance_type or ('SUBJECT' if r.subject_id else 'GENERAL'),
                    'subject_id': r.subject_id,
                    'subject_code': r.subject.subject_code if r.subject else None,
                    'subject_name': r.subject.subject_name if r.subject else None,
                    'semester': r.semester,
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
    Counts UNIQUE students for General Attendance (never inflates across multiple subjects).
    """
    today = get_current_ist_date()
    total_students = Student.query.filter_by(is_active=True).count()
    total_teachers = Teacher.query.filter_by(is_active=True).count()

    # Check if any explicit General Attendance exists today
    has_general_today = Attendance.query.filter(
        Attendance.date == today,
        Attendance.attendance_type == 'GENERAL'
    ).first() is not None

    if has_general_today:
        present_today = db.session.query(func.count(func.distinct(Attendance.student_id))).filter(
            Attendance.date == today,
            Attendance.status.in_(['Present', 'Late', 'Half Day']),
            Attendance.attendance_type == 'GENERAL'
        ).scalar() or 0

        present_records = (
            Attendance.query
            .join(Student)
            .filter(
                Attendance.date == today,
                Attendance.status.in_(['Present', 'Late', 'Half Day']),
                Attendance.attendance_type == 'GENERAL'
            )
            .order_by(Attendance.time_in.asc().nullslast())
            .all()
        )
    else:
        # If General Attendance has not yet been recorded today, strictly count UNIQUE students (excluding LEGACY)
        present_today = db.session.query(func.count(func.distinct(Attendance.student_id))).filter(
            Attendance.date == today,
            Attendance.status.in_(['Present', 'Late', 'Half Day']),
            Attendance.attendance_type != 'LEGACY'
        ).scalar() or 0

        present_records = (
            Attendance.query
            .join(Student)
            .filter(
                Attendance.date == today,
                Attendance.status.in_(['Present', 'Late', 'Half Day']),
                Attendance.attendance_type != 'LEGACY'
            )
            .order_by(Attendance.time_in.asc().nullslast())
            .all()
        )

    absent_today = max(0, total_students - present_today)
    rate = round((present_today / total_students * 100), 1) if total_students > 0 else 0.0

    # Ensure deduplicated roster (1 student = 1 entry)
    seen_students = set()
    present_students = []
    for r in present_records:
        if r.student and r.student.id not in seen_students:
            seen_students.add(r.student.id)
            present_students.append({
                'student_id': r.student.student_id,
                'full_name': r.student.full_name,
                'roll_number': r.student.roll_number,
                'department': r.student.department.name if r.student.department else None,
                'course': r.student.course,
                'attendance_type': r.attendance_type or ('SUBJECT' if r.subject_id else 'GENERAL'),
                'subject_id': r.subject_id,
                'subject_code': r.subject.subject_code if r.subject else None,
                'subject_name': r.subject.subject_name if r.subject else None,
                'semester': r.semester,
                'time_in': r.time_in.strftime('%I:%M %p') if r.time_in else '-'
            })

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

    today = get_current_ist_date()
    subject_list = []
    coordinator_list = []
    is_coordinator = False

    if current_user.is_teacher:
        teacher = current_user.teacher_profile
        if not teacher:
            return jsonify({'success': False, 'message': 'Teacher profile not linked.'}), 404

        active_coords = teacher.get_active_coordinator_assignments()
        is_coordinator = len(active_coords) > 0
        coordinator_list = [c.to_dict() for c in active_coords]
        
        assignments = teacher.get_active_assignments()
        for asgn in assignments:
            s = asgn.subject
            if not s or not s.is_active:
                continue

            # Live attendance counters for this subject assignment
            tot_q = Attendance.query.filter_by(subject_id=s.id)
            if asgn.semester:
                tot_q = tot_q.filter(
                    (Attendance.semester.ilike(asgn.semester.strip())) | (Attendance.semester.is_(None))
                )
            total_sessions = tot_q.count()
            today_sessions = tot_q.filter(Attendance.date == today).count()
            present_today = tot_q.filter(
                Attendance.date == today,
                Attendance.status.in_(['Present', 'Late', 'Half Day'])
            ).count()

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
                'section': asgn.section or '',
                'total_sessions': total_sessions,
                'today_sessions': today_sessions,
                'present_today': present_today,
                'total_classes': total_sessions,
                'scanned_today': today_sessions
            })
    elif current_user.is_admin:
        from app.models.class_coordinator import ClassCoordinator
        active_coords = ClassCoordinator.query.filter_by(is_active=True).all()
        is_coordinator = True
        coordinator_list = [c.to_dict() for c in active_coords]

        assignments = TeacherSubjectAssignment.query.filter_by(is_active=True).all()
        if assignments:
            for asgn in assignments:
                s = asgn.subject
                if not s or not s.is_active:
                    continue
                tot_q = Attendance.query.filter_by(subject_id=s.id)
                if asgn.semester:
                    tot_q = tot_q.filter(
                        (Attendance.semester.ilike(asgn.semester.strip())) | (Attendance.semester.is_(None))
                    )
                total_sessions = tot_q.count()
                today_sessions = tot_q.filter(Attendance.date == today).count()
                present_today = tot_q.filter(
                    Attendance.date == today,
                    Attendance.status.in_(['Present', 'Late', 'Half Day'])
                ).count()

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
                    'section': asgn.section or '',
                    'total_sessions': total_sessions,
                    'today_sessions': today_sessions,
                    'present_today': present_today,
                    'total_classes': total_sessions,
                    'scanned_today': today_sessions
                })
        else:
            subjects = Subject.query.filter_by(is_active=True).order_by(Subject.subject_code).all()
            for s in subjects:
                total_sessions = Attendance.query.filter_by(subject_id=s.id).count()
                today_sessions = Attendance.query.filter(Attendance.subject_id == s.id, Attendance.date == today).count()
                present_today = Attendance.query.filter(
                    Attendance.subject_id == s.id,
                    Attendance.date == today,
                    Attendance.status.in_(['Present', 'Late', 'Half Day'])
                ).count()

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
                    'section': '',
                    'total_sessions': total_sessions,
                    'today_sessions': today_sessions,
                    'present_today': present_today,
                    'total_classes': total_sessions,
                    'scanned_today': today_sessions
                })
    else:
        return jsonify({'success': False, 'message': 'Unauthorized: Only faculty can access assigned subjects.'}), 403

    return jsonify({
        'success': True,
        'count': len(subject_list),
        'subjects': subject_list,
        'is_coordinator': is_coordinator,
        'coordinator_assignments': coordinator_list
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

    today = get_current_ist_date()
    today_gen = Attendance.query.filter(
        Attendance.student_id == student.id,
        Attendance.date == today,
        (Attendance.attendance_type == 'GENERAL') | (Attendance.subject_id.is_(None))
    ).first()
    today_general_status = today_gen.status if today_gen else None

    return jsonify({
        'success': True,
        'student_id': student.student_id,
        'student_name': student.full_name,
        'overall_stats': overall_stats,
        'subject_wise': subject_wise,
        'today_general_status': today_general_status,
        'general_attendance_today': today_general_status in ('Present', 'Late', 'Half Day') if today_general_status else False,
        # Normalized aliases for Flutter mobile client
        'overall': {
            'rate': overall_stats.get('percentage', 0.0),
            'total': overall_stats.get('total_sessions', 0),
            'present': overall_stats.get('present_count', 0),
            'absent': overall_stats.get('absent_count', 0)
        },
        'subjects': [
            {
                'id': s.get('subject_id'),
                'subject_id': s.get('subject_id'),
                'subject_code': s.get('subject_code'),
                'code': s.get('subject_code'),
                'subject_name': s.get('subject_name'),
                'name': s.get('subject_name'),
                'teacher': s.get('teacher_name'),
                'teacher_name': s.get('teacher_name'),
                'total': s.get('total_classes', 0),
                'total_classes': s.get('total_classes', 0),
                'present': s.get('present_classes', 0),
                'present_classes': s.get('present_classes', 0),
                'absent': s.get('absent_classes', 0),
                'absent_classes': s.get('absent_classes', 0),
                'percentage': s.get('attendance_percentage', 0.0),
                'attendance_percentage': s.get('attendance_percentage', 0.0)
            }
            for s in subject_wise
        ]
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

    records = student.attendances.filter(
        Attendance.subject_id == subject_id,
        Attendance.attendance_type == 'SUBJECT'
    ).order_by(Attendance.date.desc()).all()
    total_classes = len(records)
    present_classes = sum(1 for a in records if a.status in ('Present', 'Late', 'Half Day'))
    absent_classes = sum(1 for a in records if a.status == 'Absent')
    pct = round((present_classes / total_classes * 100), 1) if total_classes > 0 else 0.0

    records_list = [r.to_dict() for r in records]
    stats_dict = {
        'total_classes': total_classes,
        'present_classes': present_classes,
        'absent_classes': absent_classes,
        'attendance_percentage': pct,
        'total': total_classes,
        'present': present_classes,
        'absent': absent_classes,
        'percentage': pct
    }

    return jsonify({
        'success': True,
        'subject': subject.to_dict(),
        'stats': stats_dict,
        'records': records_list,
        'history': records_list
    })
