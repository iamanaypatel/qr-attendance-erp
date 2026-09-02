from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse
from app.auth import auth_bp
from app.auth.forms import LoginForm, ChangePasswordForm
from app.extensions import db
from app.models.user import User
from app.models.audit import AuditLog

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

        # Support login by username or email
        user = User.query.filter(
            (User.username == identity) | (User.email == identity)
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
