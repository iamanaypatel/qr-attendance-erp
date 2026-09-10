import os
import uuid
from datetime import datetime, date, timedelta
from werkzeug.utils import secure_filename
from flask import render_template, redirect, url_for, flash, request, send_file, current_app
from flask_login import login_required, current_user
from app.admin import admin_bp
from app.admin.forms import StudentForm, TeacherForm, DepartmentForm, HolidayForm, AcademicSessionForm, SystemSettingsForm, SubjectForm, SubjectAssignTeachersForm, TeacherSubjectAssignmentForm
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
from app.models.subject import Subject, teacher_subjects
from app.models.subject_assignment import TeacherSubjectAssignment
from app.utils.decorators import role_required
from app.utils.qr_generator import generate_qr_bytes, generate_qr_data_uri
from app.utils.id_card import generate_student_id_card_pdf

from app.utils.photo import validate_and_save_photo, delete_student_photo

# Helper for secure image uploads
def save_uploaded_photo(file_storage, student_id=None, old_photo=None):
    if not file_storage or isinstance(file_storage, str):
        return None
    filename, err = validate_and_save_photo(file_storage, student_id=student_id or 'student', old_photo_filename=old_photo)
    if err:
        current_app.logger.warning(f"Photo upload rejected: {err}")
        return None
    return filename


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

    # Recent Scans & Present Today Roster
    recent_scans = (
        Attendance.query
        .join(Student)
        .filter(Attendance.date == today)
        .order_by(Attendance.updated_at.desc())
        .limit(10)
        .all()
    )

    present_students = (
        Attendance.query
        .join(Student)
        .filter(
            Attendance.date == today,
            Attendance.status.in_(['Present', 'Late', 'Half Day'])
        )
        .order_by(Attendance.time_in.asc().nullslast())
        .all()
    )

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
        recent_scans=recent_scans,
        present_students=present_students
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

        photo_filename = None
        if form.photo.data and not isinstance(form.photo.data, str) and hasattr(form.photo.data, 'filename') and form.photo.data.filename:
            photo_filename, photo_err = validate_and_save_photo(form.photo.data, student_id=raw_sid)
            if photo_err:
                flash(photo_err, 'danger')
                return render_template('admin/students/form.html', form=form, title='Add New Student')

        try:
            # Create portal user account if requested
            user_account = None
            if form.create_user_account.data:
                account_email = clean_email or f"{custom_username.lower()}@student.vsmt.edu.in"
                if User.query.filter(func.lower(User.email) == account_email.lower()).first():
                    account_email = f"{custom_username.lower()}.{int(datetime.utcnow().timestamp())}@student.vsmt.edu.in"

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
    try:
        if not student.qr_token:
            student.qr_token = Student.generate_qr_token()
            db.session.commit()
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
    except Exception as e:
        current_app.logger.error(f"Error viewing student {id} details: {e}", exc_info=True)
        flash(f"Notice: Could not load full statistics for student: {e}", 'warning')
        return render_template(
            'admin/students/detail.html',
            student=student,
            stats={'total_sessions': 0, 'present_count': 0, 'absent_count': 0, 'percentage': 0.0},
            qr_data_uri=generate_qr_data_uri(student.qr_token or 'STUDENT', box_size=8),
            recent_records=[]
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
        try:
            # Check duplicate student_id if changed
            if form.student_id.data.strip() != student.student_id:
                if Student.query.filter_by(student_id=form.student_id.data.strip()).first():
                    flash(f"Student ID '{form.student_id.data}' is already registered.", 'danger')
                    return render_template('admin/students/form.html', form=form, title='Edit Student', student=student)

            # Check duplicate email if changed
            clean_email = form.email.data.strip() if form.email.data else None
            if clean_email and clean_email != (student.email or ''):
                if Student.query.filter_by(email=clean_email).first():
                    flash(f"Email '{clean_email}' is already registered.", 'danger')
                    return render_template('admin/students/form.html', form=form, title='Edit Student', student=student)

            # Safe photo update: only upload if it is a real file storage object
            if form.photo.data and not isinstance(form.photo.data, str) and hasattr(form.photo.data, 'filename') and form.photo.data.filename:
                new_photo, photo_err = validate_and_save_photo(form.photo.data, student_id=student.student_id, old_photo_filename=student.photo)
                if photo_err:
                    flash(photo_err, 'danger')
                    return render_template('admin/students/form.html', form=form, title='Edit Student', student=student)
                if new_photo:
                    student.photo = new_photo

            student.student_id = form.student_id.data.strip()
            student.full_name = form.full_name.data.strip()
            student.father_name = form.father_name.data.strip() if form.father_name.data else None
            student.mother_name = form.mother_name.data.strip() if form.mother_name.data else None
            student.email = clean_email
            student.phone = form.phone.data.strip() if form.phone.data else None
            student.date_of_birth = form.date_of_birth.data
            student.gender = form.gender.data
            student.department_id = form.department_id.data
            student.course = form.course.data.strip()
            student.semester = form.semester.data
            student.section = form.section.data.strip() if form.section.data else 'A'
            student.roll_number = form.roll_number.data.strip()
            student.address = form.address.data.strip() if form.address.data else None

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
                acc_email = student.email or f"{target_username.lower()}@student.vsmt.edu.in"
                if User.query.filter(func.lower(User.email) == acc_email.lower()).first():
                    acc_email = f"{target_username.lower()}.{student.id}.{uuid.uuid4().hex[:4]}@student.vsmt.edu.in"

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
            u_email = (student.email.strip() if student.email and student.email.strip() else f"{new_username.lower()}@student.vsmt.edu.in")
            if User.query.filter(func.lower(User.email) == u_email.lower()).first():
                u_email = f"{new_username.lower()}.{student.id}.{uuid.uuid4().hex[:4]}@student.vsmt.edu.in"

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



@admin_bp.route('/students/<int:id>/photo', methods=['POST'])
@login_required
@role_required('admin')
def student_photo_update(id):
    student = Student.query.get_or_404(id)
    photo_file = request.files.get('photo')

    if not photo_file or not photo_file.filename:
        flash("Please select an image file to upload.", 'warning')
        return redirect(url_for('admin.student_detail', id=student.id))

    saved_filename, error_msg = validate_and_save_photo(
        photo_file,
        student_id=student.student_id,
        old_photo_filename=student.photo
    )

    if error_msg:
        flash(error_msg, 'danger')
        return redirect(url_for('admin.student_detail', id=student.id))

    student.photo = saved_filename
    student.updated_at = datetime.utcnow()
    db.session.commit()

    try:
        AuditLog.log('STUDENT_PHOTO_UPDATE', f"Updated photo for student {student.student_id}", user_id=current_user.id)
    except Exception:
        pass

    flash(f"Profile photo for {student.full_name} updated successfully.", 'success')
    return redirect(url_for('admin.student_detail', id=student.id))


@admin_bp.route('/students/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def student_delete(id):
    student = Student.query.get_or_404(id)
    name = student.full_name
    sid = student.student_id

    # Remove photo file if present
    if student.photo:
        delete_student_photo(student.photo)

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
                    acc_email = f"{target_username.lower()}.{teacher.id}@faculty.vsmt.edu.in"

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
            acc_email = teacher.email if teacher.email else f"{new_username.lower()}@faculty.vsmt.edu.in"
            if User.query.filter(func.lower(User.email) == acc_email.lower()).first():
                acc_email = f"{new_username.lower()}.{teacher.id}@faculty.vsmt.edu.in"

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


# ============================================================================
# Subjects Management
# ============================================================================
@admin_bp.route('/subjects')
@login_required
@role_required('admin')
def subjects():
    search = request.args.get('q', '').strip()
    dept_id = request.args.get('dept', type=int)
    semester = request.args.get('semester', '').strip()
    status = request.args.get('status', '').strip()

    query = Subject.query

    if search:
        query = query.filter(
            (Subject.subject_code.ilike(f'%{search}%')) |
            (Subject.subject_name.ilike(f'%{search}%')) |
            (Subject.course.ilike(f'%{search}%'))
        )
    if dept_id:
        query = query.filter(Subject.department_id == dept_id)
    if semester:
        query = query.filter(
            (Subject.semester == semester) |
            (Subject.id.in_(
                db.session.query(TeacherSubjectAssignment.subject_id).filter(
                    TeacherSubjectAssignment.semester.ilike(f"%{semester}%"),
                    TeacherSubjectAssignment.is_active == True
                )
            ))
        )
    if status == 'active':
        query = query.filter(Subject.is_active == True)
    elif status == 'inactive':
        query = query.filter(Subject.is_active == False)

    from sqlalchemy.orm import selectinload
    subjects_list = query.options(
        selectinload(Subject.teachers),
        selectinload(Subject.department)
    ).order_by(Subject.is_active.desc(), Subject.subject_code.asc()).all()
    departments = Department.query.order_by(Department.name).all()

    return render_template(
        'admin/subjects/index.html',
        subjects=subjects_list,
        departments=departments,
        search=search,
        selected_dept=dept_id,
        selected_semester=semester,
        selected_status=status
    )

@admin_bp.route('/subjects/create', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def subject_create():
    form = SubjectForm()
    departments = Department.query.order_by(Department.name).all()
    form.department_id.choices = [(0, '-- None / General --')] + [(d.id, f"{d.name} ({d.code})") for d in departments]

    if form.validate_on_submit():
        code = form.subject_code.data.strip().upper()
        name = form.subject_name.data.strip()

        # Check code uniqueness
        existing = Subject.query.filter(func.upper(Subject.subject_code) == code).first()
        if existing:
            flash(f"A subject with code '{code}' already exists ({existing.subject_name}).", 'danger')
            return render_template('admin/subjects/form.html', form=form, title='Add New Subject', is_edit=False)

        dept_val = form.department_id.data if form.department_id.data != 0 else None

        new_subject = Subject(
            subject_code=code,
            subject_name=name,
            description=form.description.data.strip() if form.description.data else None,
            department_id=dept_val,
            course=form.course.data.strip() if form.course.data else None,
            semester=form.semester.data if form.semester.data else None,
            is_active=form.is_active.data
        )
        db.session.add(new_subject)
        db.session.commit()

        AuditLog.log('SUBJECT_CREATE', f"Created subject {code} - {name}", user_id=current_user.id)
        flash(f"Subject '{name}' ({code}) created successfully.", 'success')
        return redirect(url_for('admin.subjects'))

    return render_template('admin/subjects/form.html', form=form, title='Add New Subject', is_edit=False)

@admin_bp.route('/subjects/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def subject_edit(id):
    subject = Subject.query.get_or_404(id)
    form = SubjectForm(obj=subject)
    departments = Department.query.order_by(Department.name).all()
    form.department_id.choices = [(0, '-- None / General --')] + [(d.id, f"{d.name} ({d.code})") for d in departments]

    if form.validate_on_submit():
        code = form.subject_code.data.strip().upper()
        name = form.subject_name.data.strip()

        # Check duplicate code on another subject
        existing = Subject.query.filter(func.upper(Subject.subject_code) == code, Subject.id != id).first()
        if existing:
            flash(f"Another subject with code '{code}' already exists ({existing.subject_name}).", 'danger')
            return render_template('admin/subjects/form.html', form=form, title=f'Edit {subject.subject_code}', is_edit=True, subject=subject)

        subject.subject_code = code
        subject.subject_name = name
        subject.description = form.description.data.strip() if form.description.data else None
        subject.department_id = form.department_id.data if form.department_id.data != 0 else None
        subject.course = form.course.data.strip() if form.course.data else None
        subject.semester = form.semester.data if form.semester.data else None
        subject.is_active = form.is_active.data
        subject.updated_at = datetime.utcnow()

        db.session.commit()
        AuditLog.log('SUBJECT_UPDATE', f"Updated subject {code} - {name}", user_id=current_user.id)
        flash(f"Subject '{name}' ({code}) updated successfully.", 'success')
        return redirect(url_for('admin.subjects'))

    if request.method == 'GET':
        form.department_id.data = subject.department_id or 0

    return render_template('admin/subjects/form.html', form=form, title=f'Edit {subject.subject_code}', is_edit=True, subject=subject)

@admin_bp.route('/subjects/<int:id>/assign-teachers', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def subject_assign_teachers(id):
    subject = Subject.query.get_or_404(id)
    form = SubjectAssignTeachersForm()

    all_teachers = Teacher.query.filter_by(is_active=True).order_by(Teacher.full_name).all()
    form.teacher_ids.choices = [(t.id, f"{t.full_name} ({t.employee_id}) — {t.department.name if t.department else 'General'}") for t in all_teachers]

    if form.validate_on_submit():
        selected_ids = set(form.teacher_ids.data or [])
        subject.teachers = [t for t in all_teachers if t.id in selected_ids]

        # Synchronize formal TeacherSubjectAssignment records
        sem = subject.semester or '4th Semester'
        # Deactivate assignments for teachers no longer selected
        for asgn in TeacherSubjectAssignment.query.filter_by(subject_id=subject.id, is_active=True).all():
            if asgn.teacher_id not in selected_ids:
                asgn.is_active = False

        # Ensure active assignment exists for each selected teacher
        for t_id in selected_ids:
            asgn = TeacherSubjectAssignment.query.filter_by(
                teacher_id=t_id,
                subject_id=subject.id,
                semester=sem
            ).first()
            if asgn:
                asgn.is_active = True
            else:
                new_asgn = TeacherSubjectAssignment(
                    teacher_id=t_id,
                    subject_id=subject.id,
                    semester=sem,
                    department_id=subject.department_id,
                    course=subject.course,
                    is_active=True
                )
                db.session.add(new_asgn)

        db.session.commit()

        AuditLog.log(
            'SUBJECT_ASSIGN_TEACHERS',
            f"Assigned {len(subject.teachers)} teachers to subject {subject.subject_code}",
            user_id=current_user.id
        )
        flash(f"Teacher assignments for {subject.subject_name} updated successfully.", 'success')
        return redirect(url_for('admin.subjects'))

    if request.method == 'GET':
        form.teacher_ids.data = [t.id for t in subject.teachers]

    return render_template(
        'admin/subjects/assign.html',
        subject=subject,
        form=form,
        teachers=all_teachers
    )

@admin_bp.route('/subjects/<int:id>/toggle-status', methods=['POST'])
@login_required
@role_required('admin')
def subject_toggle_status(id):
    subject = Subject.query.get_or_404(id)
    subject.is_active = not subject.is_active
    subject.updated_at = datetime.utcnow()
    db.session.commit()

    status_str = "activated" if subject.is_active else "deactivated"
    AuditLog.log('SUBJECT_TOGGLE', f"Subject {subject.subject_code} {status_str}", user_id=current_user.id)
    flash(f"Subject '{subject.subject_name}' ({subject.subject_code}) has been {status_str}.", 'info')
    return redirect(url_for('admin.subjects'))

@admin_bp.route('/subjects/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def subject_delete(id):
    subject = Subject.query.get_or_404(id)
    code = subject.subject_code
    name = subject.subject_name

    # Safe Deletion: Check if referenced by historical attendance
    attendance_count = subject.attendances.count()

    if attendance_count > 0:
        # Soft delete / Deactivate to protect historical attendance records
        subject.is_active = False
        subject.updated_at = datetime.utcnow()
        db.session.commit()

        AuditLog.log(
            'SUBJECT_SOFT_DELETE',
            f"Soft-deleted/Deactivated subject {code} ({attendance_count} attendance records preserved)",
            user_id=current_user.id
        )
        flash(
            f"Subject '{name}' ({code}) has {attendance_count} historical attendance records. "
            f"To protect student academic history, the subject has been safely deactivated instead of deleted.",
            'warning'
        )
    else:
        # No attendance records exist: safe to remove teacher associations and delete
        subject.teachers = []
        db.session.delete(subject)
        db.session.commit()

        AuditLog.log('SUBJECT_DELETE', f"Permanently deleted unused subject {code} - {name}", user_id=current_user.id)
        flash(f"Subject '{name}' ({code}) has been permanently deleted.", 'success')

    return redirect(url_for('admin.subjects'))

# ============================================================================
# Teacher -> Subject -> Semester Assignment Routes
# ============================================================================
@admin_bp.route('/subject-assignments', methods=['GET'])
@login_required
@role_required('admin')
def subject_assignments():
    search = request.args.get('q', '').strip()
    teacher_id = request.args.get('teacher_id', type=int)
    subject_id = request.args.get('subject_id', type=int)
    semester = request.args.get('semester', '').strip()
    status = request.args.get('status', '').strip()

    query = TeacherSubjectAssignment.query.join(Subject).join(Teacher)

    if search:
        query = query.filter(
            (Subject.subject_code.ilike(f"%{search}%")) |
            (Subject.subject_name.ilike(f"%{search}%")) |
            (Teacher.full_name.ilike(f"%{search}%")) |
            (Teacher.employee_id.ilike(f"%{search}%")) |
            (TeacherSubjectAssignment.semester.ilike(f"%{search}%"))
        )
    if teacher_id:
        query = query.filter(TeacherSubjectAssignment.teacher_id == teacher_id)
    if subject_id:
        query = query.filter(TeacherSubjectAssignment.subject_id == subject_id)
    if semester:
        query = query.filter(TeacherSubjectAssignment.semester == semester)
    if status == 'active':
        query = query.filter(TeacherSubjectAssignment.is_active == True)
    elif status == 'inactive':
        query = query.filter(TeacherSubjectAssignment.is_active == False)

    assignments = query.order_by(Subject.subject_code.asc(), TeacherSubjectAssignment.semester.asc()).all()

    all_teachers = Teacher.query.filter_by(is_active=True).order_by(Teacher.full_name).all()
    all_subjects = Subject.query.filter_by(is_active=True).order_by(Subject.subject_code).all()

    # Precompute attendance count for each assignment
    enriched = []
    for a in assignments:
        count = Attendance.query.filter_by(
            subject_id=a.subject_id,
            teacher_id=a.teacher_id
        ).count()
        enriched.append({
            'assignment': a,
            'attendance_count': count
        })

    return render_template(
        'admin/subject_assignments/index.html',
        assignments=enriched,
        teachers=all_teachers,
        subjects=all_subjects,
        search=search,
        selected_teacher_id=teacher_id,
        selected_subject_id=subject_id,
        selected_semester=semester,
        selected_status=status
    )

@admin_bp.route('/subject-assignments/create', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def subject_assignment_create():
    form = TeacherSubjectAssignmentForm()

    all_teachers = Teacher.query.filter_by(is_active=True).order_by(Teacher.full_name).all()
    all_subjects = Subject.query.filter_by(is_active=True).order_by(Subject.subject_code).all()
    all_departments = Department.query.order_by(Department.name).all()

    form.teacher_id.choices = [(t.id, f"{t.full_name} ({t.employee_id})") for t in all_teachers]
    form.subject_id.choices = [(s.id, f"{s.subject_code} — {s.subject_name} ({s.semester or 'General'})") for s in all_subjects]
    form.department_id.choices = [(0, '-- Auto from Subject --')] + [(d.id, f"{d.name} ({d.code})") for d in all_departments]

    if form.validate_on_submit():
        t_id = form.teacher_id.data
        s_id = form.subject_id.data
        sem = form.semester.data.strip()
        sec = form.section.data.strip().upper() if form.section.data else None
        dept_id = form.department_id.data if form.department_id.data != 0 else None
        course = form.course.data.strip() if form.course.data else None

        # Rule 19: Prevent accidental duplicate active assignment
        existing = TeacherSubjectAssignment.query.filter_by(
            teacher_id=t_id,
            subject_id=s_id,
            semester=sem,
            section=sec,
            is_active=True
        ).first()

        if existing:
            flash(f"An active assignment already exists for this Teacher, Subject, Semester ({sem}), and Section ({sec or 'All'}).", "danger")
            return render_template('admin/subject_assignments/form.html', form=form, title='Assign Subject to Teacher', is_edit=False)

        subject = Subject.query.get(s_id)
        teacher = Teacher.query.get(t_id)

        if not dept_id and subject and subject.department_id:
            dept_id = subject.department_id
        if not course and subject and subject.course:
            course = subject.course

        new_assignment = TeacherSubjectAssignment(
            teacher_id=t_id,
            subject_id=s_id,
            semester=sem,
            department_id=dept_id,
            course=course,
            section=sec,
            is_active=form.is_active.data
        )
        db.session.add(new_assignment)

        # Synchronize with secondary association table for legacy support
        if subject and teacher and teacher not in subject.teachers:
            subject.teachers.append(teacher)

        db.session.commit()

        AuditLog.log(
            'SUBJECT_ASSIGNMENT_CREATE',
            f"Assigned {subject.subject_code} to {teacher.full_name} for {sem}",
            user_id=current_user.id
        )
        flash(f"Successfully assigned {subject.subject_name} ({subject.subject_code}) to {teacher.full_name} for {sem}.", "success")
        return redirect(url_for('admin.subject_assignments'))

    return render_template('admin/subject_assignments/form.html', form=form, title='Assign Subject to Teacher', is_edit=False)

@admin_bp.route('/subject-assignments/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def subject_assignment_edit(id):
    assignment = TeacherSubjectAssignment.query.get_or_404(id)
    form = TeacherSubjectAssignmentForm(obj=assignment)

    all_teachers = Teacher.query.filter_by(is_active=True).order_by(Teacher.full_name).all()
    all_subjects = Subject.query.filter_by(is_active=True).order_by(Subject.subject_code).all()
    all_departments = Department.query.order_by(Department.name).all()

    form.teacher_id.choices = [(t.id, f"{t.full_name} ({t.employee_id})") for t in all_teachers]
    form.subject_id.choices = [(s.id, f"{s.subject_code} — {s.subject_name}") for s in all_subjects]
    form.department_id.choices = [(0, '-- Auto from Subject --')] + [(d.id, f"{d.name} ({d.code})") for d in all_departments]

    if form.validate_on_submit():
        t_id = form.teacher_id.data
        s_id = form.subject_id.data
        sem = form.semester.data.strip()
        sec = form.section.data.strip().upper() if form.section.data else None

        # Check collision with other assignments
        duplicate = TeacherSubjectAssignment.query.filter(
            TeacherSubjectAssignment.id != id,
            TeacherSubjectAssignment.teacher_id == t_id,
            TeacherSubjectAssignment.subject_id == s_id,
            TeacherSubjectAssignment.semester == sem,
            TeacherSubjectAssignment.section == sec,
            TeacherSubjectAssignment.is_active == True
        ).first()

        if duplicate:
            flash(f"Another active assignment already exists for this Teacher, Subject, Semester ({sem}), and Section.", "danger")
            return render_template('admin/subject_assignments/form.html', form=form, title='Edit Subject Assignment', is_edit=True, assignment=assignment)

        assignment.teacher_id = t_id
        assignment.subject_id = s_id
        assignment.semester = sem
        assignment.section = sec
        assignment.department_id = form.department_id.data if form.department_id.data != 0 else None
        assignment.course = form.course.data.strip() if form.course.data else None
        assignment.is_active = form.is_active.data
        assignment.updated_at = datetime.utcnow()

        # Synchronize secondary association table
        subject = Subject.query.get(s_id)
        teacher = Teacher.query.get(t_id)
        if subject and teacher and teacher not in subject.teachers:
            subject.teachers.append(teacher)

        db.session.commit()

        AuditLog.log(
            'SUBJECT_ASSIGNMENT_UPDATE',
            f"Updated assignment ID {id}: {subject.subject_code} to {teacher.full_name} ({sem})",
            user_id=current_user.id
        )
        flash("Subject assignment updated successfully.", "success")
        return redirect(url_for('admin.subject_assignments'))

    if request.method == 'GET':
        form.department_id.data = assignment.department_id or 0

    return render_template('admin/subject_assignments/form.html', form=form, title='Edit Subject Assignment', is_edit=True, assignment=assignment)

@admin_bp.route('/subject-assignments/<int:id>/toggle-status', methods=['POST'])
@login_required
@role_required('admin')
def subject_assignment_toggle_status(id):
    assignment = TeacherSubjectAssignment.query.get_or_404(id)
    assignment.is_active = not assignment.is_active
    assignment.updated_at = datetime.utcnow()
    db.session.commit()

    status_str = "activated" if assignment.is_active else "deactivated"
    AuditLog.log(
        'SUBJECT_ASSIGNMENT_TOGGLE',
        f"Assignment {assignment.subject.subject_code} for {assignment.teacher.full_name} {status_str}",
        user_id=current_user.id
    )
    flash(f"Assignment for {assignment.subject.subject_name} ({assignment.semester}) has been {status_str}.", "info")
    return redirect(url_for('admin.subject_assignments'))

@admin_bp.route('/subject-assignments/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def subject_assignment_delete(id):
    assignment = TeacherSubjectAssignment.query.get_or_404(id)
    sub_code = assignment.subject.subject_code if assignment.subject else "Subject"
    t_name = assignment.teacher.full_name if assignment.teacher else "Teacher"
    sem = assignment.semester

    # Safe deletion: check if historical attendance records exist
    att_count = Attendance.query.filter_by(
        subject_id=assignment.subject_id,
        teacher_id=assignment.teacher_id
    ).count()

    if att_count > 0:
        # Soft-delete / deactivate to preserve historical attendance
        assignment.is_active = False
        assignment.updated_at = datetime.utcnow()
        db.session.commit()

        AuditLog.log(
            'SUBJECT_ASSIGNMENT_SOFT_DELETE',
            f"Deactivated assignment for {sub_code} - {t_name} ({att_count} attendance records preserved)",
            user_id=current_user.id
        )
        flash(
            f"Assignment for '{sub_code}' ({t_name}, {sem}) has {att_count} historical attendance records. "
            f"To preserve student academic history, the assignment has been deactivated instead of deleted.",
            "warning"
        )
    else:
        db.session.delete(assignment)
        db.session.commit()
        AuditLog.log(
            'SUBJECT_ASSIGNMENT_DELETE',
            f"Deleted unused assignment for {sub_code} - {t_name} ({sem})",
            user_id=current_user.id
        )
        flash(f"Assignment for '{sub_code}' ({t_name}, {sem}) has been permanently deleted.", "success")

    return redirect(url_for('admin.subject_assignments'))

