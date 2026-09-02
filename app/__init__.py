import os
from datetime import datetime
from flask import Flask, redirect, url_for, render_template, request, jsonify
from flask_login import current_user
from app.config import config, BASE_DIR
from app.extensions import db, migrate, login_manager, csrf

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config.get(config_name, config['default']))

    # Ensure required instance and upload directories exist
    instance_dir = BASE_DIR / 'instance'
    instance_dir.mkdir(parents=True, exist_ok=True)
    upload_dir = app.config['UPLOAD_FOLDER']
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Reverse proxy header support for HTTPS behind Render/PaaS load balancers
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    # Register blueprints
    from app.auth import auth_bp
    from app.admin import admin_bp
    from app.teacher import teacher_bp
    from app.student import student_bp
    from app.attendance import attendance_bp
    from app.reports import reports_bp
    from app.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(api_bp)

    # Root route redirects to role dashboard or login
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            if current_user.is_admin:
                return redirect(url_for('admin.dashboard'))
            elif current_user.is_teacher:
                return redirect(url_for('teacher.dashboard'))
            elif current_user.is_student:
                return redirect(url_for('student.dashboard'))
        return redirect(url_for('auth.login'))

    # Global context processor
    @app.context_processor
    def inject_global_vars():
        from app.models.settings import SystemSetting
        from app.models.session import AcademicSession
        
        inst_name = SystemSetting.get_setting('institution_name', app.config.get('INSTITUTION_NAME'))
        inst_email = SystemSetting.get_setting('institution_email', app.config.get('INSTITUTION_EMAIL'))
        active_session = AcademicSession.query.filter_by(is_active=True).first()

        return {
            'institution_name': inst_name,
            'institution_email': inst_email,
            'active_session': active_session,
            'current_year': datetime.now().year,
            'now': datetime.now()
        }

    # Error handlers
    register_error_handlers(app)

    return app

def register_error_handlers(app):
    def make_error_response(error_code, title, message):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'error_code': error_code,
                'message': message
            }), error_code
        return render_template(
            f'errors/{error_code}.html' if os.path.exists(f'app/templates/errors/{error_code}.html') else 'errors/general.html',
            error_code=error_code,
            title=title,
            message=message
        ), error_code

    @app.errorhandler(400)
    def bad_request(e):
        return make_error_response(400, 'Bad Request', 'The server could not understand the request or invalid form data was supplied.')

    @app.errorhandler(401)
    def unauthorized(e):
        return make_error_response(401, 'Unauthorized', 'You must log in with valid credentials to access this resource.')

    @app.errorhandler(403)
    def forbidden(e):
        return make_error_response(403, 'Access Forbidden', 'You do not have administrative or role-level permissions to access this page.')

    @app.errorhandler(404)
    def not_found(e):
        return make_error_response(404, 'Page Not Found', 'The page or resource you are looking for does not exist or has been moved.')

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return make_error_response(500, 'Server Error', 'An unexpected internal server error occurred. Our team has been notified.')
