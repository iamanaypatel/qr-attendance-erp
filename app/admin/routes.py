import os
import uuid
from datetime import datetime, date, timedelta
from werkzeug.utils import secure_filename
from flask import render_template, redirect, url_for, flash, request, send_file, current_app
from flask_login import login_required, current_user
from app.admin import admin_bp
from app.admin.forms import StudentForm, TeacherForm, DepartmentForm, HolidayForm, AcademicSessionForm, SystemSettingsForm
from sqlalchemy import func
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
        raw_sid = form.student_id.data.strip() if form.student_id.data else ''
        clean_email = form.email.data.strip() if form.email.data and form.email.data.strip() else None

        # Check unique student_id
        if Student.query.filter_by(student_id=raw_sid).first():
            flash(f"Student ID '{raw_sid}' is already registered. Please use a unique Student ID.", 'danger')
            return render_template('admin/students/form.html', form=form, title='Add New Student')

        # Check unique email only if provided
        if clean_email and Student.query.filter_by(email=clean_email).first():
            flash(f"Email '{clean_email}' is already in use by another student.", 'danger')
            return render_template('admin/students/form.html', form=form, title='Add New Student')

        # Custom username & password for student portal login
        custom_username = form.portal_username.data.strip() if form.portal_username.data and form.portal_username.data.strip() else raw_sid
        custom_password = form.portal_password.data.strip() if form.portal_password.data and form.portal_password.data.strip() else 'Student@1234'

        # Check unique username in User table if account creation is enabled
        if form.create_user_account.data:
            existing_user = User.query.filter(func.lower(User.username) == custom_username.lower()).first()
            if existing_user:
                flash(f"Portal Username '{custom_username}' is already taken. Please choose another username.", 'danger')
                return render_template('admin/students/form.html', form=form, title='Add New Student')

        photo_filename = save_uploaded_photo(form.photo.data)

        try:
            # Create portal user account if requested
            user_account = None
            if form.create_user_account.data:
                account_email = clean_email or f"{custom_username.lower()}@student.apex.edu"
                if User.query.filter(func.lower(User.email) == account_email.lower()).first():
                    account_email = f"{custom_username.lower()}.{int(datetime.utcnow().timestamp())}@student.apex.edu"

                user_account = User(
                    username=custom_username,
                    email=account_email,
                    role='student',
                    is_active=True
                )
                user_account.set_password(custom_password)
                db.session.add(user_account)
                db.session.flush()

            student = Student(
                user_id=user_account.id if user_account else None,
                student_id=raw_sid,
                full_name=form.full_name.data.strip(),
                father_name=form.father_name.data.strip() if form.father_name.data else None,
                mother_name=form.mother_name.data.strip() if form.mother_name.data else None,
                email=clean_email,
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

            try:
                AuditLog.log('STUDENT_CREATE', f"Created student {student.full_name} ({student.student_id})", user_id=current_user.id)
            except Exception:
                pass

            flash(f"Student '{student.full_name}' added successfully! (Login: {custom_username if user_account else 'None'})", 'success')
            return redirect(url_for('admin.student_detail', id=student.id))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating student: {e}", exc_info=True)
            flash(f"Could not create student: {str(e)}", 'danger')
            return render_template('admin/students/form.html', form=form, title='Add New Student')

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

    if request.method == 'GET':
        if student.user:
            form.portal_username.data = student.user.username
            form.create_user_account.data = True
        else:
            form.create_user_account.data = False

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

        try:
            # Manage Portal Login Account & Password
            target_username = form.portal_username.data.strip() if form.portal_username.data and form.portal_username.data.strip() else student.student_id
            if student.user:
                # Check username collision if changed
                if target_username.lower() != student.user.username.lower():
                    conflict = User.query.filter(
                        (func.lower(User.username) == target_username.lower()) & (User.id != student.user.id)
                    ).first()
                    if conflict:
                        flash(f"Username '{target_username}' is already in use by another user.", 'danger')
                        return render_template('admin/students/form.html', form=form, title='Edit Student', student=student)
                    student.user.username = target_username

                # If student's email was updated and is unique, sync user account email
                if student.email:
                    email_conflict = User.query.filter((func.lower(User.email) == student.email.lower()) & (User.id != student.user.id)).first()
                    if not email_conflict:
                        student.user.email = student.email

                if form.portal_password.data and form.portal_password.data.strip():
                    student.user.set_password(form.portal_password.data.strip())
                    flash(f"Updated portal password for student {student.full_name}.", 'info')
            elif form.create_user_account.data or (form.portal_username.data and form.portal_username.data.strip()):
                # Create user account for student
                conflict = User.query.filter(func.lower(User.username) == target_username.lower()).first()
                if conflict:
                    flash(f"Username '{target_username}' is already in use by another user.", 'danger')
                    return render_template('admin/students/form.html', form=form, title='Edit Student', student=student)

                new_pass = form.portal_password.data.strip() if form.portal_password.data and form.portal_password.data.strip() else 'Student@1234'
                acc_email = student.email or f"{target_username.lower()}@student.apex.edu"
                if User.query.filter(func.lower(User.email) == acc_email.lower()).first():
                    acc_email = f"{target_username.lower()}.{student.id}@student.apex.edu"

                new_user = User(
                    username=target_username,
                    email=acc_email,
                    role='student',
                    is_active=True
                )
                new_user.set_password(new_pass)
                db.session.add(new_user)
                db.session.flush()
                student.user_id = new_user.id
                flash(f"Created new portal login account for {student.full_name} (Username: {target_username}).", 'info')

            db.session.commit()
            try:
                AuditLog.log('STUDENT_UPDATE', f"Updated student {student.student_id}", user_id=current_user.id)
            except Exception:
                pass
            flash(f"Student details updated successfully.", 'success')
            return redirect(url_for('admin.student_detail', id=student.id))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating student: {e}", exc_info=True)
            flash(f"Could not update student: {str(e)}", 'danger')
            return render_template('admin/students/form.html', form=form, title='Edit Student', student=student)

    return render_template('admin/students/form.html', form=form, title='Edit Student', student=student)

@admin_bp.route('/students/<int:id>/credentials', methods=['POST'])
@login_required
@role_required('admin')
def student_credentials_update(id):
    student = Student.query.get_or_404(id)
    new_username = request.form.get('username', '').strip()
    new_password = request.form.get('password', '').strip()

    if not new_username:
        flash("Username cannot be empty.", 'danger')
        return redirect(url_for('admin.student_detail', id=student.id))

    # Check username collision
    conflict = User.query.filter(
        (func.lower(User.username) == new_username.lower()) &
        (User.id != (student.user.id if student.user else -1))
    ).first()
    if conflict:
        flash(f"Username '{new_username}' is already taken by another user.", 'danger')
        return redirect(url_for('admin.student_detail', id=student.id))

    try:
        if student.user:
            student.user.username = new_username
            if new_password:
                student.user.set_password(new_password)
            db.session.commit()
            try:
                AuditLog.log('CREDENTIALS_UPDATE', f"Updated credentials for student {student.student_id}", user_id=current_user.id)
            except Exception:
                pass
            flash(f"Login credentials for {student.full_name} updated successfully! (Username: {new_username})", 'success')
        else:
            pwd = new_password if new_password else 'Student@1234'
            u_email = (student.email.strip() if student.email and student.email.strip() else f"{new_username.lower()}@student.apex.edu")
            if User.query.filter(func.lower(User.email) == u_email.lower()).first():
                u_email = f"{new_username.lower()}.{student.id}@student.apex.edu"

            user = User(
                username=new_username,
                email=u_email,
                role='student',
                is_active=True
            )
            user.set_password(pwd)
            db.session.add(user)
            db.session.flush()
            student.user_id = user.id
            db.session.commit()
            try:
                AuditLog.log('CREDENTIALS_CREATE', f"Created login for student {student.student_id}", user_id=current_user.id)
            except Exception:
                pass
            flash(f"Portal login account created for {student.full_name}! (Username: {new_username})", 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update credentials for student {student.id}: {e}", exc_info=True)
        flash(f"Failed to update credentials: {str(e)}", 'danger')

    return redirect(url_for('admin.student_detail', id=student.id))


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

        # Custom username & password for teacher portal login
        custom_username = form.portal_username.data.strip() if form.portal_username.data and form.portal_username.data.strip() else form.employee_id.data.strip().lower()
        password_to_set = form.password.data.strip() if form.password.data and form.password.data.strip() else 'Teacher@1234'

        # Check unique username across User table
        existing_u = User.query.filter(func.lower(User.username) == custom_username.lower()).first()
        if existing_u:
            flash(f"Portal Username '{custom_username}' is already taken. Please choose another username.", 'danger')
            return render_template('admin/teachers/form.html', form=form, title='Add New Teacher')

        # Check unique email across User table
        teacher_email = form.email.data.strip()
        existing_email_u = User.query.filter(func.lower(User.email) == teacher_email.lower()).first()
        if existing_email_u:
            flash(f"Email '{teacher_email}' is already associated with another user account.", 'danger')
            return render_template('admin/teachers/form.html', form=form, title='Add New Teacher')

        try:
            user = User(
                username=custom_username,
                email=teacher_email,
                role='teacher',
                is_active=form.is_active.data
            )
            user.set_password(password_to_set)
            db.session.add(user)
            db.session.flush()

            teacher = Teacher(
                user_id=user.id,
                employee_id=form.employee_id.data.strip(),
                full_name=form.full_name.data.strip(),
                email=teacher_email,
                phone=form.phone.data.strip() if form.phone.data else None,
                department_id=form.department_id.data,
                designation=form.designation.data.strip(),
                is_active=form.is_active.data
            )
            db.session.add(teacher)
            db.session.commit()

            try:
                AuditLog.log('TEACHER_CREATE', f"Created teacher {teacher.full_name} ({teacher.employee_id})", user_id=current_user.id)
            except Exception:
                pass

            flash(f"Teacher '{teacher.full_name}' added successfully! (Login: {custom_username})", 'success')
            return redirect(url_for('admin.teachers'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating teacher: {e}", exc_info=True)
            flash(f"Could not create teacher: {str(e)}", 'danger')
            return render_template('admin/teachers/form.html', form=form, title='Add New Teacher')

    return render_template('admin/teachers/form.html', form=form, title='Add New Teacher')

@admin_bp.route('/teachers/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def teacher_edit(id):
    teacher = Teacher.query.get_or_404(id)
    form = TeacherForm(obj=teacher)
    departments = Department.query.order_by(Department.name).all()
    form.department_id.choices = [(d.id, f"{d.name} ({d.code})") for d in departments]

    if request.method == 'GET' and teacher.user:
        form.portal_username.data = teacher.user.username

    if form.validate_on_submit():
        if form.employee_id.data.strip() != teacher.employee_id:
            if Teacher.query.filter_by(employee_id=form.employee_id.data.strip()).first():
                flash(f"Employee ID '{form.employee_id.data}' already exists.", 'danger')
                return render_template('admin/teachers/form.html', form=form, title='Edit Teacher', teacher=teacher)

        if form.email.data.strip() != teacher.email:
            if Teacher.query.filter_by(email=form.email.data.strip()).first():
                flash(f"Email '{form.email.data}' already exists.", 'danger')
                return render_template('admin/teachers/form.html', form=form, title='Edit Teacher', teacher=teacher)

        try:
            teacher.employee_id = form.employee_id.data.strip()
            teacher.full_name = form.full_name.data.strip()
            teacher.email = form.email.data.strip()
            teacher.phone = form.phone.data.strip() if form.phone.data else None
            teacher.department_id = form.department_id.data
            teacher.designation = form.designation.data.strip()
            teacher.is_active = form.is_active.data

            # Update Portal Username & Password
            target_username = form.portal_username.data.strip() if form.portal_username.data and form.portal_username.data.strip() else teacher.employee_id.lower()
            if teacher.user:
                if target_username.lower() != teacher.user.username.lower():
                    conflict = User.query.filter(
                        (func.lower(User.username) == target_username.lower()) & (User.id != teacher.user.id)
                    ).first()
                    if conflict:
                        flash(f"Portal Username '{target_username}' is already taken by another user.", 'danger')
                        return render_template('admin/teachers/form.html', form=form, title='Edit Teacher', teacher=teacher)
                    teacher.user.username = target_username

                teacher.user.is_active = form.is_active.data
                # Update user email if unique
                email_conflict = User.query.filter((func.lower(User.email) == teacher.email.lower()) & (User.id != teacher.user.id)).first()
                if not email_conflict:
                    teacher.user.email = teacher.email

                if form.password.data and form.password.data.strip():
                    teacher.user.set_password(form.password.data.strip())
                    flash(f"Updated portal password for teacher {teacher.full_name}.", 'info')
            else:
                conflict = User.query.filter(func.lower(User.username) == target_username.lower()).first()
                if conflict:
                    flash(f"Portal Username '{target_username}' is already taken.", 'danger')
                    return render_template('admin/teachers/form.html', form=form, title='Edit Teacher', teacher=teacher)
                
                acc_email = teacher.email
                if User.query.filter(func.lower(User.email) == acc_email.lower()).first():
                    acc_email = f"{target_username.lower()}.{teacher.id}@faculty.apex.edu"

                new_u = User(
                    username=target_username,
                    email=acc_email,
                    role='teacher',
                    is_active=teacher.is_active
                )
                new_pass = form.password.data.strip() if form.password.data and form.password.data.strip() else 'Teacher@1234'
                new_u.set_password(new_pass)
                db.session.add(new_u)
                db.session.flush()
                teacher.user_id = new_u.id
                flash(f"Created portal login account for teacher {teacher.full_name} (Username: {target_username}).", 'info')

            db.session.commit()
            try:
                AuditLog.log('TEACHER_UPDATE', f"Updated teacher {teacher.employee_id}", user_id=current_user.id)
            except Exception:
                pass

            flash('Teacher updated successfully.', 'success')
            return redirect(url_for('admin.teachers'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating teacher: {e}", exc_info=True)
            flash(f"Could not update teacher: {str(e)}", 'danger')
            return render_template('admin/teachers/form.html', form=form, title='Edit Teacher', teacher=teacher)

    return render_template('admin/teachers/form.html', form=form, title='Edit Teacher', teacher=teacher)

@admin_bp.route('/teachers/<int:id>/credentials', methods=['POST'])
@login_required
@role_required('admin')
def teacher_credentials_update(id):
    teacher = Teacher.query.get_or_404(id)
    new_username = request.form.get('username', '').strip()
    new_password = request.form.get('password', '').strip()

    if not new_username:
        flash("Username cannot be empty.", 'danger')
        return redirect(request.referrer or url_for('admin.teachers'))

    conflict = User.query.filter(
        (func.lower(User.username) == new_username.lower()) &
        (User.id != (teacher.user.id if teacher.user else -1))
    ).first()
    if conflict:
        flash(f"Username '{new_username}' is already taken by another user.", 'danger')
        return redirect(request.referrer or url_for('admin.teachers'))

    try:
        if teacher.user:
            teacher.user.username = new_username
            if new_password:
                teacher.user.set_password(new_password)
            db.session.commit()
            try:
                AuditLog.log('CREDENTIALS_UPDATE', f"Updated credentials for teacher {teacher.employee_id}", user_id=current_user.id)
            except Exception:
                pass
            flash(f"Login credentials for teacher {teacher.full_name} updated successfully! (Username: {new_username})", 'success')
        else:
            pwd = new_password if new_password else 'Teacher@1234'
            acc_email = teacher.email if teacher.email else f"{new_username.lower()}@faculty.apex.edu"
            if User.query.filter(func.lower(User.email) == acc_email.lower()).first():
                acc_email = f"{new_username.lower()}.{teacher.id}@faculty.apex.edu"

            user = User(
                username=new_username,
                email=acc_email,
                role='teacher',
                is_active=teacher.is_active
            )
            user.set_password(pwd)
            db.session.add(user)
            db.session.flush()
            teacher.user_id = user.id
            db.session.commit()
            try:
                AuditLog.log('CREDENTIALS_CREATE', f"Created login for teacher {teacher.employee_id}", user_id=current_user.id)
            except Exception:
                pass
            flash(f"Portal login account created for teacher {teacher.full_name}! (Username: {new_username})", 'success')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update credentials for teacher {teacher.id}: {e}", exc_info=True)
        flash(f"Failed to update credentials: {str(e)}", 'danger')

    return redirect(request.referrer or url_for('admin.teachers'))


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
