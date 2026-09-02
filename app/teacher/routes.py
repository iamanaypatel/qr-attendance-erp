from datetime import datetime, date
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.teacher import teacher_bp
from app.models.student import Student
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

    query = Attendance.query.filter_by(date=today)
    if dept_id:
        query = query.join(Student).filter(Student.department_id == dept_id)

    today_records = query.order_by(Attendance.time_in.desc().nullslast()).all()
    today_scan_count = len(today_records)

    return render_template(
        'teacher/dashboard.html',
        today_records=today_records,
        today_scan_count=today_scan_count,
        now=datetime.now()
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
