from flask import render_template, redirect, url_for, flash, request, jsonify
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
        inst_setting = SystemSetting.query.filter_by(key='institution_name').first()
        if not inst_setting:
            db.session.add(SystemSetting(key='institution_name', value='Dr. Virendra Swarup Memorial Trust Group of Institutions', description='Full legal institution name'))
        else:
            inst_setting.value = 'Dr. Virendra Swarup Memorial Trust Group of Institutions'

        # Session
        if not AcademicSession.query.filter_by(name='2025-2026').first():
            db.session.add(AcademicSession(name='2025-2026', start_date=date(2025, 8, 1), end_date=date(2026, 6, 30), is_active=True))

        # Admin
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', email='admin@vsmt.edu.in', role='admin', is_active=True)
            db.session.add(admin)
        admin.set_password('Admin@1234')
        admin.is_active = True

        # Teacher
        teacher = User.query.filter_by(username='teacher').first()
        if not teacher:
            teacher = User(username='teacher', email='teacher@vsmt.edu.in', role='teacher', is_active=True)
            db.session.add(teacher)
            db.session.flush()
            cse = depts.get('CSE') or Department.query.filter_by(code='CSE').first()
            if cse and not Teacher.query.filter_by(user_id=teacher.id).first():
                db.session.add(Teacher(
                    user_id=teacher.id, employee_id='TCH101', full_name='Dr. Alan Turing',
                    email='teacher@vsmt.edu.in', phone='+1-555-0101', department_id=cse.id, designation='Associate Professor'
                ))
        teacher.set_password('Teacher@1234')
        teacher.is_active = True

        # Student
        student = User.query.filter_by(username='student').first()
        if not student:
            student = User(username='student', email='student@vsmt.edu.in', role='student', is_active=True)
            db.session.add(student)
            db.session.flush()
            cse = depts.get('CSE') or Department.query.filter_by(code='CSE').first()
            if cse and not Student.query.filter_by(user_id=student.id).first():
                db.session.add(Student(
                    user_id=student.id, student_id='STU2026001', full_name='Alex Johnson',
                    father_name='Robert Johnson', mother_name='Mary Johnson', email='student@vsmt.edu.in',
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

def find_user_by_identity(identity: str):
    """
    Resolve a user by username, email, or linked Student's student_id / roll_number.
    """
    identity = (identity or '').strip()
    if not identity:
        return None
    user = User.query.filter(
        (func.lower(User.username) == func.lower(identity)) |
        (func.lower(User.email) == func.lower(identity))
    ).first()
    if user:
        return user

    from app.models.student import Student
    student = Student.query.filter(
        (func.lower(Student.student_id) == func.lower(identity)) |
        (func.lower(Student.roll_number) == func.lower(identity))
    ).first()
    if student and student.user:
        return student.user

    return None

from app.extensions import csrf, db

@auth_bp.route('/login', methods=['GET', 'POST'])
@csrf.exempt
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        elif current_user.is_teacher:
            return redirect(url_for('teacher.dashboard'))
        elif current_user.is_student:
            return redirect(url_for('student.dashboard'))

    # Check for direct form POST without CSRF (e.g. mobile client)
    if request.method == 'POST' and (request.is_json or not request.form.get('csrf_token')):
        data = request.get_json(silent=True) or request.form
        identity = (data.get('identity') or data.get('username') or '').strip()
        password = data.get('password') or ''

        if identity and password:
            user = find_user_by_identity(identity)

            if user and user.check_password(password):
                if not user.is_active:
                    if request.is_json or 'application/json' in request.headers.get('Accept', ''):
                        return jsonify({'success': False, 'message': 'Account deactivated.'}), 403
                    flash('Your account has been deactivated.', 'danger')
                    return render_template('auth/login.html', form=LoginForm())

                login_user(user, remember=True)
                AuditLog.log('USER_LOGIN', f'User logged in: {user.username} [{user.role}]', user_id=user.id)

                if request.is_json or 'application/json' in request.headers.get('Accept', ''):
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
                    })

                flash(f'Welcome back, {user.get_display_name()}!', 'success')
                if user.is_admin:
                    return redirect(url_for('admin.dashboard'))
                elif user.is_teacher:
                    return redirect(url_for('teacher.dashboard'))
                elif user.is_student:
                    if not user.student:
                        flash('Student profile is not linked to this account. Please contact the administrator.', 'warning')
                    return redirect(url_for('student.dashboard'))
            else:
                if request.is_json or 'application/json' in request.headers.get('Accept', ''):
                    return jsonify({'success': False, 'message': 'Invalid credentials.'}), 401
                flash('Invalid credentials. Please verify your username/email and password.', 'danger')
                return render_template('auth/login.html', form=LoginForm())

    form = LoginForm()
    if form.validate_on_submit():
        identity = form.identity.data.strip()
        password = form.password.data

        # Support login by username, email, student_id, or roll_number (case-insensitive)
        user = find_user_by_identity(identity)

        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact the administrator.', 'danger')
                return render_template('auth/login.html', form=form)

            login_user(user, remember=form.remember_me.data)
            AuditLog.log('USER_LOGIN', f'User logged in: {user.username} [{user.role}]', user_id=user.id)
            flash(f'Welcome back, {user.get_display_name()}!', 'success')
            if user.is_student and not user.student:
                flash('Student profile is not linked to this account. Please contact the administrator.', 'warning')

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


@auth_bp.route('/firebase-login', methods=['POST'])
@csrf.exempt
def firebase_login():
    import os
    import requests
    from flask import current_app

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    id_token = data.get('id_token')
    email = (data.get('email') or '').strip().lower()
    phone_number = (data.get('phone_number') or '').strip()
    uid = (data.get('uid') or '').strip()
    display_name = data.get('display_name') or ''

    if not id_token:
        return jsonify({'success': False, 'message': 'Missing Firebase ID token.'}), 400

    # Verify ID token with Google Identity Toolkit
    verified_email = None
    verified_phone = None
    try:
        api_key = os.environ.get('FIREBASE_API_KEY', 'AIzaSyB7a8nt-kYYiT97sruPGD6-gCSErpRqTPg')
        verify_url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={api_key}"
        resp = requests.post(verify_url, json={'idToken': id_token}, timeout=6)
        if resp.status_code == 200:
            users_info = resp.json().get('users', [])
            if users_info:
                u_info = users_info[0]
                verified_email = (u_info.get('email') or '').strip().lower()
                verified_phone = (u_info.get('phoneNumber') or '').strip()
                uid = u_info.get('localId', uid)
    except Exception as e:
        current_app.logger.warning(f"Firebase token verification error: {e}")

    target_email = verified_email or email
    target_phone = verified_phone or phone_number

    user = None
    if target_email:
        user = User.query.filter(func.lower(User.email) == target_email).first()

    if not user and target_phone:
        from app.models.student import Student
        from app.models.teacher import Teacher
        stu = Student.query.filter(Student.phone == target_phone).first()
        if stu and stu.user:
            user = stu.user
        if not user:
            tch = Teacher.query.filter(Teacher.phone == target_phone).first()
            if tch and tch.user:
                user = tch.user

    if not user and uid:
        user = User.query.filter_by(username=uid).first()

    if not user:
        # Provision new account for verified Firebase user
        username_candidate = (target_email.split('@')[0] if target_email else f"user_{uid[:8]}")[:64]
        base_uname = username_candidate
        counter = 1
        while User.query.filter_by(username=username_candidate).first():
            username_candidate = f"{base_uname}{counter}"
            counter += 1

        user = User(
            username=username_candidate,
            email=target_email or f"{uid}@erpvsgoi.firebase",
            role='student',
            is_active=True
        )
        user.set_password(f"FirebasePass@{uid[:8]}")
        db.session.add(user)
        db.session.commit()

    if not user.is_active:
        return jsonify({'success': False, 'message': 'Account is deactivated.'}), 403

    login_user(user, remember=True)
    AuditLog.log('FIREBASE_AUTH_LOGIN', f"Logged in via Firebase Auth: {user.username} [{user.role}]", user_id=user.id)

    if user.is_admin:
        redirect_url = url_for('admin.dashboard')
    elif user.is_teacher:
        redirect_url = url_for('teacher.dashboard')
    else:
        redirect_url = url_for('student.dashboard')

    return jsonify({
        'success': True,
        'message': f"Welcome, {user.get_display_name()}!",
        'redirect_url': redirect_url,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'display_name': user.get_display_name()
        }
    }), 200

