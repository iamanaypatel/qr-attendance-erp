import os
import uuid
from datetime import datetime, date, timedelta
from werkzeug.utils import secure_filename
from flask import render_template, redirect, url_for, flash, request, send_file, current_app
from flask_login import login_required, current_user
from app.admin import admin_bp
from app.admin.forms import StudentForm, TeacherForm, DepartmentForm, HolidayForm, AcademicSessionForm, SystemSettingsForm
from app.extensions import db
from app.models.user import User
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.department import Department
from app.models.attendance import Attendance
from app.models.holiday import Holiday
from app.models.session import AcademicSession
from app.models.settings import SystemSetting
from app.models.audit import AuditLog
from app.utils.decorators import role_required
from app.utils.qr_generator import generate_qr_bytes, generate_qr_data_uri
from app.utils.id_card import generate_student_id_card_pdf

# Helper for secure image uploads
def save_uploaded_photo(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    ext = file_storage.filename.rsplit('.', 1)[-1].lower()
    if ext not in current_app.config['ALLOWED_EXTENSIONS']:
        return None
    unique_name = f"{uuid.uuid4().hex}_{secure_filename(file_storage.filename)}"
    upload_folder = current_app.config['UPLOAD_FOLDER']
    file_storage.save(upload_folder / unique_name)
    return unique_name

# ============================================================================
# Dashboard Route
# ============================================================================
@admin_bp.route('/dashboard')
@login_required
@role_required('admin')
def dashboard():
    today = date.today()
    total_students = Student.query.filter_by(is_active=True).count()
    total_teachers = Teacher.query.filter_by(is_active=True).count()
    
    # Present today (status in Present, Late, Half Day)
    present_today = Attendance.query.filter(
        Attendance.date == today,
        Attendance.status.in_(['Present', 'Late', 'Half Day'])
    ).count()
    absent_today = max(0, total_students - present_today)
    attendance_rate = round((present_today / total_students * 100), 1) if total_students > 0 else 0.0

    # 7-Day Trend
    trend_labels = []
    trend_data = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        trend_labels.append(d.strftime('%a (%d/%m)'))
        count = Attendance.query.filter(
            Attendance.date == d,
            Attendance.status.in_(['Present', 'Late', 'Half Day'])
        ).count()
        trend_data.append(count)

    # Department breakdown
    dept_labels = []
    dept_data = []
    departments = Department.query.all()
    for dept in departments:
        dept_labels.append(dept.code)
        c = Attendance.query.join(Student).filter(
            Student.department_id == dept.id,
            Attendance.date == today,
            Attendance.status.in_(['Present', 'Late', 'Half Day'])
        ).count()
        dept_data.append(c)

    # Recent Scans
    recent_scans = Attendance.query.filter(Attendance.date == today).order_by(Attendance.time_in.desc().nullslast()).limit(8).all()

    return render_template(
        'admin/dashboard.html',
        total_students=total_students,
        total_teachers=total_teachers,
        present_today=present_today,
        absent_today=absent_today,
        attendance_rate=attendance_rate,
        trend_labels=trend_labels,
        trend_data=trend_data,
        dept_labels=dept_labels,
        dept_data=dept_data,
        recent_scans=recent_scans
    )

# ============================================================================
# Students Management Routes
# ============================================================================
@admin_bp.route('/students')
@login_required
@role_required('admin')
def students():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()
    dept_id = request.args.get('dept', type=int)
    semester = request.args.get('sem', '').strip()

    query = Student.query

    if search:
        search_fmt = f"%{search}%"
        query = query.filter(
            (Student.full_name.ilike(search_fmt)) |
            (Student.student_id.ilike(search_fmt)) |
            (Student.roll_number.ilike(search_fmt)) |
            (Student.email.ilike(search_fmt))
        )
    if dept_id:
        query = query.filter(Student.department_id == dept_id)
    if semester:
        query = query.filter(Student.semester == semester)

    pagination = query.order_by(Student.student_id.asc()).paginate(page=page, per_page=12, error_out=False)
    departments = Department.query.order_by(Department.name).all()

    return render_template(
        'admin/students/index.html',
        pagination=pagination,
        students=pagination.items,
        departments=departments,
        search=search,
        selected_dept=dept_id,
        selected_sem=semester
    )

@admin_bp.route('/students/create', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def student_create():
    form = StudentForm()
    departments = Department.query.order_by(Department.name).all()
    form.department_id.choices = [(d.id, f"{d.name} ({d.code})") for d in departments]

    if not departments:
        flash('Please create at least one Department before adding students.', 'warning')
        return redirect(url_for('admin.departments'))

    if form.validate_on_submit():
        # Check unique student_id
        if Student.query.filter_by(student_id=form.student_id.data.strip()).first():
            flash(f"Student ID '{form.student_id.data}' is already registered.", 'danger')
            return render_template('admin/students/form.html', form=form, title='Add New Student')

        # Check unique email
        if form.email.data and Student.query.filter_by(email=form.email.data.strip()).first():
            flash(f"Email '{form.email.data}' is already in use by another student.", 'danger')
            return render_template('admin/students/form.html', form=form, title='Add New Student')

        photo_filename = save_uploaded_photo(form.photo.data)

        # Create user account if requested
        user_account = None
        if form.create_user_account.data and form.email.data:
            existing_user = User.query.filter(
                (User.username == form.student_id.data.strip()) | (User.email == form.email.data.strip())
            ).first()
            if not existing_user:
                user_account = User(
                    username=form.student_id.data.strip(),
                    email=form.email.data.strip(),
                    role='student',
                    is_active=True
                )
                user_account.set_password('Student@1234')
                db.session.add(user_account)
                db.session.flush()

        student = Student(
            user_id=user_account.id if user_account else None,
            student_id=form.student_id.data.strip(),
            full_name=form.full_name.data.strip(),
            father_name=form.father_name.data.strip() if form.father_name.data else None,
            mother_name=form.mother_name.data.strip() if form.mother_name.data else None,
            email=form.email.data.strip() if form.email.data else None,
            phone=form.phone.data.strip() if form.phone.data else None,
            date_of_birth=form.date_of_birth.data,
            gender=form.gender.data,
            department_id=form.department_id.data,
            course=form.course.data.strip(),
            semester=form.semester.data,
            section=form.section.data.strip() if form.section.data else 'A',
            roll_number=form.roll_number.data.strip(),
            address=form.address.data.strip() if form.address.data else None,
            photo=photo_filename,
            qr_token=Student.generate_qr_token(),
            is_active=True
        )
        db.session.add(student)
        db.session.commit()

        AuditLog.log('STUDENT_CREATE', f"Created student {student.full_name} ({student.student_id})", user_id=current_user.id)
        flash(f"Student '{student.full_name}' added successfully!", 'success')
        return redirect(url_for('admin.student_detail', id=student.id))

    return render_template('admin/students/form.html', form=form, title='Add New Student')

@admin_bp.route('/students/<int:id>')
@login_required
@role_required('admin')
def student_detail(id):
    student = Student.query.get_or_404(id)
    stats = student.calculate_attendance_stats()
    qr_data_uri = generate_qr_data_uri(student.qr_token, box_size=8)
    recent_records = student.attendances.order_by(Attendance.date.desc()).limit(15).all()

    return render_template(
        'admin/students/detail.html',
        student=student,
        stats=stats,
        qr_data_uri=qr_data_uri,
        recent_records=recent_records
    )

@admin_bp.route('/students/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def student_edit(id):
    student = Student.query.get_or_404(id)
    form = StudentForm(obj=student)
    departments = Department.query.order_by(Department.name).all()
    form.department_id.choices = [(d.id, f"{d.name} ({d.code})") for d in departments]

    if form.validate_on_submit():
        # Check duplicate student_id if changed
        if form.student_id.data.strip() != student.student_id:
            if Student.query.filter_by(student_id=form.student_id.data.strip()).first():
                flash(f"Student ID '{form.student_id.data}' is already registered.", 'danger')
                return render_template('admin/students/form.html', form=form, title='Edit Student', student=student)

        # Check duplicate email if changed
        if form.email.data and form.email.data.strip() != student.email:
            if Student.query.filter_by(email=form.email.data.strip()).first():
                flash(f"Email '{form.email.data}' is already registered.", 'danger')
                return render_template('admin/students/form.html', form=form, title='Edit Student', student=student)

        if form.photo.data:
            new_photo = save_uploaded_photo(form.photo.data)
            if new_photo:
                student.photo = new_photo

        student.student_id = form.student_id.data.strip()
        student.full_name = form.full_name.data.strip()
        student.father_name = form.father_name.data.strip() if form.father_name.data else None
        student.mother_name = form.mother_name.data.strip() if form.mother_name.data else None
        student.email = form.email.data.strip() if form.email.data else None
        student.phone = form.phone.data.strip() if form.phone.data else None
        student.date_of_birth = form.date_of_birth.data
        student.gender = form.gender.data
        student.department_id = form.department_id.data
        student.course = form.course.data.strip()
        student.semester = form.semester.data
        student.section = form.section.data.strip() if form.section.data else 'A'
        student.roll_number = form.roll_number.data.strip()
        student.address = form.address.data.strip() if form.address.data else None

        db.session.commit()
        AuditLog.log('STUDENT_UPDATE', f"Updated student {student.student_id}", user_id=current_user.id)
        flash(f"Student details updated successfully.", 'success')
        return redirect(url_for('admin.student_detail', id=student.id))

    return render_template('admin/students/form.html', form=form, title='Edit Student', student=student)

@admin_bp.route('/students/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def student_delete(id):
    student = Student.query.get_or_404(id)
    name = student.full_name
    sid = student.student_id

    # If student has a user account, delete it as well
    if student.user:
        db.session.delete(student.user)
    db.session.delete(student)
    db.session.commit()

    AuditLog.log('STUDENT_DELETE', f"Deleted student {name} ({sid})", user_id=current_user.id)
    flash(f"Student {name} ({sid}) deleted successfully.", 'info')
    return redirect(url_for('admin.students'))

@admin_bp.route('/students/<int:id>/qr.png')
@login_required
@role_required('admin', 'teacher')
def student_qr_download(id):
    student = Student.query.get_or_404(id)
    buf = generate_qr_bytes(student.qr_token, box_size=10, border=2)
    return send_file(
        buf,
        mimetype='image/png',
        as_attachment=True,
        download_name=f"QR_{student.student_id}.png"
    )

@admin_bp.route('/students/<int:id>/id-card.pdf')
@login_required
@role_required('admin', 'teacher')
def student_id_card_pdf(id):
    student = Student.query.get_or_404(id)
    inst_name = SystemSetting.get_setting('institution_name', current_app.config['INSTITUTION_NAME'])
    pdf_buffer = generate_student_id_card_pdf(student, institution_name=inst_name)
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"ID_Card_{student.student_id}.pdf"
    )

# ============================================================================
# Teachers Management Routes
# ============================================================================
@admin_bp.route('/teachers')
@login_required
@role_required('admin')
def teachers():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()
    dept_id = request.args.get('dept', type=int)

    query = Teacher.query
    if search:
        search_fmt = f"%{search}%"
        query = query.filter(
            (Teacher.full_name.ilike(search_fmt)) |
            (Teacher.employee_id.ilike(search_fmt)) |
            (Teacher.email.ilike(search_fmt))
        )
    if dept_id:
        query = query.filter(Teacher.department_id == dept_id)

    pagination = query.order_by(Teacher.employee_id.asc()).paginate(page=page, per_page=12, error_out=False)
    departments = Department.query.order_by(Department.name).all()

    return render_template(
        'admin/teachers/index.html',
        pagination=pagination,
        teachers=pagination.items,
        departments=departments,
        search=search,
        selected_dept=dept_id
    )

@admin_bp.route('/teachers/create', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def teacher_create():
    form = TeacherForm()
    departments = Department.query.order_by(Department.name).all()
    form.department_id.choices = [(d.id, f"{d.name} ({d.code})") for d in departments]

    if not departments:
        flash('Please create at least one Department before adding teachers.', 'warning')
        return redirect(url_for('admin.departments'))

    if form.validate_on_submit():
        if Teacher.query.filter_by(employee_id=form.employee_id.data.strip()).first():
            flash(f"Employee ID '{form.employee_id.data}' is already registered.", 'danger')
            return render_template('admin/teachers/form.html', form=form, title='Add New Teacher')

        if Teacher.query.filter_by(email=form.email.data.strip()).first():
            flash(f"Email '{form.email.data}' is already registered for another teacher.", 'danger')
            return render_template('admin/teachers/form.html', form=form, title='Add New Teacher')

        # Create linked User account for teacher login
        user = User.query.filter_by(email=form.email.data.strip()).first()
        if not user:
            user = User(
                username=form.employee_id.data.strip().lower(),
                email=form.email.data.strip(),
                role='teacher',
                is_active=form.is_active.data
            )
            password_to_set = form.password.data if form.password.data else 'Teacher@1234'
            user.set_password(password_to_set)
            db.session.add(user)
            db.session.flush()

        teacher = Teacher(
            user_id=user.id,
            employee_id=form.employee_id.data.strip(),
            full_name=form.full_name.data.strip(),
            email=form.email.data.strip(),
            phone=form.phone.data.strip() if form.phone.data else None,
            department_id=form.department_id.data,
            designation=form.designation.data.strip(),
            is_active=form.is_active.data
        )
        db.session.add(teacher)
        db.session.commit()

        AuditLog.log('TEACHER_CREATE', f"Created teacher {teacher.full_name} ({teacher.employee_id})", user_id=current_user.id)
        flash(f"Teacher '{teacher.full_name}' added successfully!", 'success')
        return redirect(url_for('admin.teachers'))

    return render_template('admin/teachers/form.html', form=form, title='Add New Teacher')

@admin_bp.route('/teachers/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def teacher_edit(id):
    teacher = Teacher.query.get_or_404(id)
    form = TeacherForm(obj=teacher)
    departments = Department.query.order_by(Department.name).all()
    form.department_id.choices = [(d.id, f"{d.name} ({d.code})") for d in departments]

    if form.validate_on_submit():
        if form.employee_id.data.strip() != teacher.employee_id:
            if Teacher.query.filter_by(employee_id=form.employee_id.data.strip()).first():
                flash(f"Employee ID '{form.employee_id.data}' already exists.", 'danger')
                return render_template('admin/teachers/form.html', form=form, title='Edit Teacher', teacher=teacher)

        if form.email.data.strip() != teacher.email:
            if Teacher.query.filter_by(email=form.email.data.strip()).first():
                flash(f"Email '{form.email.data}' already exists.", 'danger')
                return render_template('admin/teachers/form.html', form=form, title='Edit Teacher', teacher=teacher)

        teacher.employee_id = form.employee_id.data.strip()
        teacher.full_name = form.full_name.data.strip()
        teacher.email = form.email.data.strip()
        teacher.phone = form.phone.data.strip() if form.phone.data else None
        teacher.department_id = form.department_id.data
        teacher.designation = form.designation.data.strip()
        teacher.is_active = form.is_active.data

        if teacher.user:
            teacher.user.is_active = form.is_active.data
            teacher.user.email = teacher.email
            if form.password.data:
                teacher.user.set_password(form.password.data)

        db.session.commit()
        AuditLog.log('TEACHER_UPDATE', f"Updated teacher {teacher.employee_id}", user_id=current_user.id)
        flash('Teacher updated successfully.', 'success')
        return redirect(url_for('admin.teachers'))

    return render_template('admin/teachers/form.html', form=form, title='Edit Teacher', teacher=teacher)

@admin_bp.route('/teachers/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def teacher_delete(id):
    teacher = Teacher.query.get_or_404(id)
    name = teacher.full_name
    empid = teacher.employee_id

    if teacher.user:
        db.session.delete(teacher.user)
    db.session.delete(teacher)
    db.session.commit()

    AuditLog.log('TEACHER_DELETE', f"Deleted teacher {name} ({empid})", user_id=current_user.id)
    flash(f"Teacher {name} deleted successfully.", 'info')
    return redirect(url_for('admin.teachers'))

# ============================================================================
# Departments Management Routes
# ============================================================================
@admin_bp.route('/departments', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def departments():
    form = DepartmentForm()
    if form.validate_on_submit():
        code = form.code.data.strip().upper()
        if Department.query.filter_by(code=code).first():
            flash(f"Department code '{code}' already exists.", 'danger')
        else:
            dept = Department(
                name=form.name.data.strip(),
                code=code,
                description=form.description.data.strip() if form.description.data else None
            )
            db.session.add(dept)
            db.session.commit()
            AuditLog.log('DEPARTMENT_CREATE', f"Created department {code}", user_id=current_user.id)
            flash(f"Department '{dept.name}' created successfully.", 'success')
            return redirect(url_for('admin.departments'))

    depts = Department.query.order_by(Department.name).all()
    return render_template('admin/departments/index.html', departments=depts, form=form)

@admin_bp.route('/departments/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def department_delete(id):
    dept = Department.query.get_or_404(id)
    if dept.students.count() > 0 or dept.teachers.count() > 0:
        flash(f"Cannot delete department '{dept.name}' because it has active students or teachers assigned.", 'warning')
        return redirect(url_for('admin.departments'))

    db.session.delete(dept)
    db.session.commit()
    AuditLog.log('DEPARTMENT_DELETE', f"Deleted department {dept.code}", user_id=current_user.id)
    flash(f"Department '{dept.name}' deleted.", 'info')
    return redirect(url_for('admin.departments'))

# ============================================================================
# QR Generator Central Hub
# ============================================================================
@admin_bp.route('/qr-generator')
@login_required
@role_required('admin')
def qr_generator():
    dept_id = request.args.get('dept', type=int)
    search = request.args.get('q', '').strip()

    query = Student.query.filter_by(is_active=True)
    if dept_id:
        query = query.filter_by(department_id=dept_id)
    if search:
        query = query.filter(
            (Student.full_name.ilike(f"%{search}%")) |
            (Student.student_id.ilike(f"%{search}%"))
        )

    students = query.order_by(Student.student_id).limit(60).all()
    departments = Department.query.order_by(Department.name).all()

    # Pre-generate data URIs for all displayed students
    student_qrs = []
    for s in students:
        student_qrs.append({
            'student': s,
            'qr_uri': generate_qr_data_uri(s.qr_token, box_size=5, border=1)
        })

    return render_template(
        'admin/qr_generator.html',
        student_qrs=student_qrs,
        departments=departments,
        selected_dept=dept_id,
        search=search
    )

# ============================================================================
# System Settings & Audit Logs
# ============================================================================
@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def settings():
    form = SystemSettingsForm()
    if form.validate_on_submit():
        SystemSetting.set_setting('institution_name', form.institution_name.data.strip())
        SystemSetting.set_setting('institution_email', form.institution_email.data.strip())
        SystemSetting.set_setting('institution_phone', form.institution_phone.data.strip())
        SystemSetting.set_setting('institution_address', form.institution_address.data.strip())
        SystemSetting.set_setting('attendance_start_time', form.attendance_start_time.data.strip())
        SystemSetting.set_setting('attendance_end_time', form.attendance_end_time.data.strip())
        SystemSetting.set_setting('duplicate_scan_cooldown_seconds', form.duplicate_scan_cooldown_seconds.data.strip())

        AuditLog.log('SETTINGS_UPDATE', "System settings updated", user_id=current_user.id)
        flash('Institution and system settings updated successfully.', 'success')
        return redirect(url_for('admin.settings'))

    if request.method == 'GET':
        form.institution_name.data = SystemSetting.get_setting('institution_name', current_app.config['INSTITUTION_NAME'])
        form.institution_email.data = SystemSetting.get_setting('institution_email', current_app.config['INSTITUTION_EMAIL'])
        form.institution_phone.data = SystemSetting.get_setting('institution_phone', current_app.config['INSTITUTION_PHONE'])
        form.institution_address.data = SystemSetting.get_setting('institution_address', current_app.config['INSTITUTION_ADDRESS'])
        form.attendance_start_time.data = SystemSetting.get_setting('attendance_start_time', '08:00')
        form.attendance_end_time.data = SystemSetting.get_setting('attendance_end_time', '18:00')
        form.duplicate_scan_cooldown_seconds.data = SystemSetting.get_setting('duplicate_scan_cooldown_seconds', '60')

    sessions = AcademicSession.query.order_by(AcademicSession.start_date.desc()).all()
    audit_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(25).all()

    return render_template('admin/settings.html', form=form, sessions=sessions, audit_logs=audit_logs)
