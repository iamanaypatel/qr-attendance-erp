from functools import wraps
from flask import abort, redirect, url_for, flash, request
from flask_login import current_user

def role_required(*allowed_roles):
    """
    Decorator to enforce role-based access control.
    Supports single or multiple roles, e.g. @role_required('admin'), @role_required('admin', 'teacher').
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login', next=request.url))

            if current_user.role not in allowed_roles:
                if request.is_json or request.path.startswith('/api/'):
                    return {'success': False, 'message': 'Forbidden: You do not have permission for this resource.'}, 403
                flash('Access denied: You do not have authorization to view that page.', 'danger')
                # Redirect user to their own role dashboard
                if current_user.is_admin:
                    return redirect(url_for('admin.dashboard'))
                elif current_user.is_teacher:
                    return redirect(url_for('teacher.dashboard'))
                elif current_user.is_student:
                    return redirect(url_for('student.dashboard'))
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator
