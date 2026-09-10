from datetime import datetime, date
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.teacher import teacher_bp
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.subject import Subject
from app.models.attendance import Attendance
from app.utils.decorators import role_required

@teacher_bp.route('/dashboard')
@login_required
@role_required('teacher', 'admin')
def dashboard():
    today = date.today()
    teacher = current_user.teacher_profile

    # Department scoped records
    dept_id = teacher.department_id if teacher else None

    query = Attendance.query.join(Student).filter(Attendance.date == today)
    if dept_id:
        query = query.filter(Student.department_id == dept_id)

    today_records = query.order_by(Attendance.time_in.desc().nullslast()).all()
    today_scan_count = len(today_records)

    assigned_subjects = []
    if teacher:
        assigned_subjects = teacher.assigned_subjects.filter_by(is_active=True).order_by(Subject.subject_code).all()
    elif current_user.is_admin:
        assigned_subjects = Subject.query.filter_by(is_active=True).order_by(Subject.subject_code).all()

    return render_template(
        'teacher/dashboard.html',
        today_records=today_records,
        today_scan_count=today_scan_count,
        assigned_subjects=assigned_subjects,
        now=datetime.now()
    )

@teacher_bp.route('/subjects')
@login_required
@role_required('teacher', 'admin')
def subjects():
    teacher = current_user.teacher_profile

    if teacher:
        my_subjects = teacher.assigned_subjects.filter_by(is_active=True).order_by(Subject.subject_code).all()
    elif current_user.is_admin:
        my_subjects = Subject.query.filter_by(is_active=True).order_by(Subject.subject_code).all()
    else:
        my_subjects = []

    # Get summary stats for each subject
    subject_stats = []
    for s in my_subjects:
        total_sessions = Attendance.query.filter_by(subject_id=s.id).count()
        today_sessions = Attendance.query.filter_by(subject_id=s.id, date=date.today()).count()
        subject_stats.append({
            'subject': s,
            'total_sessions': total_sessions,
            'today_sessions': today_sessions
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

    # SECURITY CHECK: Verify teacher is authorized for this subject
    if not current_user.is_admin:
        if not teacher or not teacher.is_assigned_to_subject(subject_id):
            flash(f"Security Alert: You are not authorized to access attendance for '{subject.subject_name}'.", "danger")
            return redirect(url_for('teacher.subjects'))

    # Filters
    filter_date_str = request.args.get('date', '').strip()
    search = request.args.get('q', '').strip()
    status = request.args.get('status', '').strip()
    page = request.args.get('page', 1, type=int)

    query = Attendance.query.join(Student).filter(Attendance.subject_id == subject_id)

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

    # Compute overall subject metrics
    all_subject_records = Attendance.query.filter_by(subject_id=subject_id).all()
    total_records = len(all_subject_records)
    present_records = sum(1 for a in all_subject_records if a.status in ('Present', 'Late', 'Half Day'))
    absent_records = sum(1 for a in all_subject_records if a.status == 'Absent')
    attendance_pct = round((present_records / total_records * 100), 1) if total_records > 0 else 0.0

    return render_template(
        'teacher/subject_attendance.html',
        subject=subject,
        pagination=pagination,
        records=pagination.items,
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
