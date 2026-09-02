from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse
from sqlalchemy import func
from app.auth import auth_bp
from app.auth.forms import LoginForm, ChangePasswordForm
from app.extensions import db
from app.models.user import User
from app.models.audit import AuditLog

@auth_bp.route('/init-system')
def init_system():
    """Manual trigger to bootstrap database tables and ensure default accounts exist."""
    try:
        db.create_all()
        from app.models.department import Department
        from app.models.student import Student
        from app.models.teacher import Teacher
        from app.models.settings import SystemSetting
        from app.models.session import AcademicSession
        from datetime import date

        # Departments
        depts_data = [
            ('Computer Science & Engineering', 'CSE', 'Department of Computer Science and Software Engineering'),
            ('Electronics & Communication', 'ECE', 'Department of Electronics and Communications Engineering'),
            ('Mechanical Engineering', 'MECH', 'Department of Mechanical Engineering & Robotics'),
            ('Business Administration', 'BBA', 'Department of Management and Business Studies')
        ]
        depts = {}
        for name, code, desc in depts_data:
            d = Department.query.filter_by(code=code).first()
            if not d:
                d = Department(name=name, code=code, description=desc)
                db.session.add(d)
                db.session.flush()
            depts[code] = d

        # Settings
        if not SystemSetting.query.filter_by(key='institution_name').first():
            db.session.add(SystemSetting(key='institution_name', value='Apex Institute of Technology & Management', description='Full legal institution name'))

        # Session
        if not AcademicSession.query.filter_by(name='2025-2026').first():
            db.session.add(AcademicSession(name='2025-2026', start_date=date(2025, 8, 1), end_date=date(2026, 6, 30), is_active=True))

        # Admin
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', email='admin@apex-institute.edu', role='admin', is_active=True)
            db.session.add(admin)
        admin.set_password('Admin@1234')
        admin.is_active = True

        # Teacher
        teacher = User.query.filter_by(username='teacher').first()
        if not teacher:
            teacher = User(username='teacher', email='teacher@apex-institute.edu', role='teacher', is_active=True)
            db.session.add(teacher)
            db.session.flush()
            cse = depts.get('CSE') or Department.query.filter_by(code='CSE').first()
            if cse and not Teacher.query.filter_by(user_id=teacher.id).first():
                db.session.add(Teacher(
                    user_id=teacher.id, employee_id='TCH101', full_name='Dr. Alan Turing',
                    email='teacher@apex-institute.edu', phone='+1-555-0101', department_id=cse.id, designation='Associate Professor'
                ))
        teacher.set_password('Teacher@1234')
        teacher.is_active = True

        # Student
        student = User.query.filter_by(username='student').first()
        if not student:
            student = User(username='student', email='student@apex-institute.edu', role='student', is_active=True)
            db.session.add(student)
            db.session.flush()
            cse = depts.get('CSE') or Department.query.filter_by(code='CSE').first()
            if cse and not Student.query.filter_by(user_id=student.id).first():
                db.session.add(Student(
                    user_id=student.id, student_id='STU2026001', full_name='Alex Johnson',
                    father_name='Robert Johnson', mother_name='Mary Johnson', email='student@apex-institute.edu',
                    phone='+1-555-0202', date_of_birth=date(2004, 5, 14), gender='Male', department_id=cse.id,
                    course='B.Tech Computer Science', semester='4th', section='A', roll_number='CS-2024-042',
                    address='42 Innovation Drive, Tech City', qr_token=Student.generate_qr_token(),
                    admission_date=date(2024, 8, 1), is_active=True
                ))
        student.set_password('Student@1234')
        student.is_active = True

        db.session.commit()
        flash('System accounts initialized successfully! You can now log in with admin / Admin@1234.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Initialization note: {str(e)}', 'warning')
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        elif current_user.is_teacher:
            return redirect(url_for('teacher.dashboard'))
        elif current_user.is_student:
            return redirect(url_for('student.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        identity = form.identity.data.strip()
        password = form.password.data

        # Support login by username or email (case-insensitive)
        user = User.query.filter(
            (func.lower(User.username) == func.lower(identity)) |
            (func.lower(User.email) == func.lower(identity))
        ).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact the administrator.', 'danger')
                return render_template('auth/login.html', form=form)

            login_user(user, remember=form.remember_me.data)
            AuditLog.log('USER_LOGIN', f'User logged in: {user.username} [{user.role}]', user_id=user.id)
            flash(f'Welcome back, {user.get_display_name()}!', 'success')

            # Handle next parameter safely (prevent open redirect attacks)
            next_page = request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                if user.is_admin:
                    next_page = url_for('admin.dashboard')
                elif user.is_teacher:
                    next_page = url_for('teacher.dashboard')
                elif user.is_student:
                    next_page = url_for('student.dashboard')
                else:
                    next_page = url_for('auth.login')

            return redirect(next_page)
        else:
            flash('Invalid credentials. Please verify your username/email and password.', 'danger')

    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    AuditLog.log('USER_LOGOUT', f'User logged out: {current_user.username}', user_id=current_user.id)
    logout_user()
    flash('You have been signed out securely.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Your current password does not match our records.', 'danger')
            return render_template('auth/change_password.html', form=form)

        if form.new_password.data != form.confirm_password.data:
            flash('New passwords do not match.', 'danger')
            return render_template('auth/change_password.html', form=form)

        current_user.set_password(form.new_password.data)
        db.session.commit()
        AuditLog.log('PASSWORD_CHANGE', f'Password changed for {current_user.username}', user_id=current_user.id)
        flash('Password updated successfully.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/change_password.html', form=form)
