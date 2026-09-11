from datetime import datetime, date
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.teacher import teacher_bp
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.subject import Subject
from app.models.attendance import Attendance
from app.utils.decorators import role_required
from app.utils.timezone import get_current_ist_date, get_current_ist_datetime

@teacher_bp.route('/dashboard')
@login_required
@role_required('teacher', 'admin')
def dashboard():
    today = get_current_ist_date()
    teacher = current_user.teacher_profile

    # Department scoped records
    dept_id = teacher.department_id if teacher else None

    query = Attendance.query.join(Student).filter(Attendance.date == today)
    if dept_id:
        query = query.filter(Student.department_id == dept_id)

    today_records = query.order_by(Attendance.time_in.desc().nullslast()).all()
    today_scan_count = len(today_records)

    assigned_assignments = []
    coordinator_assignments = []
    if teacher:
        assigned_assignments = teacher.get_active_assignments()
        coordinator_assignments = teacher.get_active_coordinator_assignments()
    elif current_user.is_admin:
        from app.models.subject_assignment import TeacherSubjectAssignment
        from app.models.class_coordinator import ClassCoordinator
        assigned_assignments = TeacherSubjectAssignment.query.filter_by(is_active=True).all()
        coordinator_assignments = ClassCoordinator.query.filter_by(is_active=True).all()

    return render_template(
        'teacher/dashboard.html',
        today_records=today_records,
        today_scan_count=today_scan_count,
        assigned_assignments=assigned_assignments,
        coordinator_assignments=coordinator_assignments,
        now=get_current_ist_datetime()
    )

@teacher_bp.route('/subjects')
@login_required
@role_required('teacher', 'admin')
def subjects():
    today = get_current_ist_date()
    teacher = current_user.teacher_profile
    from app.models.subject_assignment import TeacherSubjectAssignment

    if teacher:
        active_assignments = teacher.get_active_assignments()
    elif current_user.is_admin:
        active_assignments = TeacherSubjectAssignment.query.filter_by(is_active=True).all()
    else:
        active_assignments = []

    # Get summary stats for each assignment (subject + semester)
    subject_stats = []
    for asgn in active_assignments:
        s = asgn.subject
        if not s or not s.is_active:
            continue
        from sqlalchemy import func
        query = Attendance.query.filter(
            Attendance.subject_id == s.id,
            Attendance.attendance_type == 'SUBJECT'
        )
        if asgn.semester:
            query = query.filter(
                (Attendance.semester.ilike(asgn.semester.strip())) | (Attendance.semester.is_(None))
            )
        total_sessions = query.with_entities(func.count(func.distinct(Attendance.date))).scalar() or 0
        today_scans = query.filter(Attendance.date == today).count()
        today_sessions = today_scans # Represents students scanned today for the 'Scanned Today' KPI
        subject_stats.append({
            'assignment': asgn,
            'subject': s,
            'semester': asgn.semester,
            'teacher': asgn.teacher,
            'total_sessions': total_sessions,
            'today_sessions': today_sessions,
            'scanned_today': today_scans,
            'conducted_today': 1 if today_scans > 0 else 0
        })

    return render_template(
        'teacher/subjects.html',
        subject_stats=subject_stats,
        teacher=teacher
    )

@teacher_bp.route('/subjects/<int:subject_id>/attendance')
@login_required
@role_required('teacher', 'admin')
def subject_attendance(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    teacher = current_user.teacher_profile
    semester = request.args.get('semester', '').strip()

    # SECURITY CHECK: Verify teacher is authorized for this subject and semester
    if not current_user.is_admin:
        if not teacher or not teacher.is_assigned_to_subject(subject_id, semester=semester if semester else None):
            flash(f"Security Alert: You are not authorized to access attendance for '{subject.subject_name}'.", "danger")
            return redirect(url_for('teacher.subjects'))

    # Filters
    filter_date_str = request.args.get('date', '').strip()
    search = request.args.get('q', '').strip()
    status = request.args.get('status', '').strip()
    page = request.args.get('page', 1, type=int)

    query = Attendance.query.join(Student).filter(Attendance.subject_id == subject_id)
    if semester:
        query = query.filter(Attendance.semester.ilike(semester))

    filter_date = None
    if filter_date_str:
        try:
            filter_date = datetime.strptime(filter_date_str, '%Y-%m-%d').date()
            query = query.filter(Attendance.date == filter_date)
        except ValueError:
            filter_date = None

    if search:
        query = query.filter(
            (Student.full_name.ilike(f"%{search}%")) |
            (Student.student_id.ilike(f"%{search}%")) |
            (Student.roll_number.ilike(f"%{search}%"))
        )

    if status:
        query = query.filter(Attendance.status == status)

    pagination = query.order_by(Attendance.date.desc(), Attendance.time_in.desc().nullslast()).paginate(
        page=page, per_page=20, error_out=False
    )

    # Compute overall subject metrics (scoped to semester if provided)
    metrics_query = Attendance.query.filter_by(subject_id=subject_id)
    if semester:
        metrics_query = metrics_query.filter(
            (Attendance.semester.ilike(semester.strip())) | (Attendance.semester.is_(None))
        )
    from sqlalchemy import func
    total_sessions = metrics_query.filter(Attendance.attendance_type == 'SUBJECT').with_entities(
        func.count(func.distinct(Attendance.date))
    ).scalar() or 0

    all_subject_records = metrics_query.all()
    total_records = len(all_subject_records)
    present_records = sum(1 for a in all_subject_records if a.status in ('Present', 'Late', 'Half Day'))
    absent_records = sum(1 for a in all_subject_records if a.status == 'Absent')
    attendance_pct = round((present_records / total_records * 100), 1) if total_records > 0 else 0.0

    return render_template(
        'teacher/subject_attendance.html',
        subject=subject,
        pagination=pagination,
        records=pagination.items,
        total_sessions=total_sessions,
        total_records=total_records,
        present_records=present_records,
        absent_records=absent_records,
        attendance_pct=attendance_pct,
        filter_date=filter_date_str,
        search=search,
        selected_status=status
    )

@teacher_bp.route('/students')
@login_required
@role_required('teacher', 'admin')
def students():
    teacher = current_user.teacher_profile
    dept_id = teacher.department_id if teacher else None

    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()

    query = Student.query.filter_by(is_active=True)
    if dept_id:
        query = query.filter_by(department_id=dept_id)

    if search:
        query = query.filter(
            (Student.full_name.ilike(f"%{search}%")) |
            (Student.student_id.ilike(f"%{search}%")) |
            (Student.roll_number.ilike(f"%{search}%"))
        )

    pagination = query.order_by(Student.roll_number).paginate(page=page, per_page=15, error_out=False)

    return render_template(
        'teacher/students.html',
        pagination=pagination,
        students=pagination.items,
        search=search,
        department=teacher.department if teacher else None
    )
