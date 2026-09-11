import os
import click
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

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith('/api/') or request.is_json:
            return jsonify({
                'success': False,
                'action': 'UNAUTHORIZED',
                'message': 'Authentication session expired or invalid. Please log in again.'
            }), 401
        return redirect(url_for('auth.login', next=request.url))

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
        if not inst_name or 'Apex' in inst_name or 'Technology' in inst_name:
            inst_name = "Dr. Virendra Swarup Memorial Trust Group of Institutions"
        inst_email = SystemSetting.get_setting('institution_email', app.config.get('INSTITUTION_EMAIL'))
        if not inst_email or 'apex' in inst_email:
            inst_email = "contact@vsmt.edu.in"
        active_session = AcademicSession.query.filter_by(is_active=True).first()

        return {
            'institution_name': inst_name,
            'institution_email': inst_email,
            'active_session': active_session,
            'current_year': datetime.now().year,
            'now': datetime.now()
        }

    # Auto-bootstrap database tables and default accounts if missing
    if not app.config.get('TESTING'):
        _auto_bootstrap_database(app)

    # Error handlers
    register_error_handlers(app)

    # CLI commands
    @app.cli.group("attendance")
    def attendance_cli():
        """Attendance management CLI."""
        pass

    @attendance_cli.command("classify-historical")
    @click.option("--dry-run", is_flag=True, help="Simulate classification without modifying database.")
    @click.option("--force", is_flag=True, help="Force re-evaluation of all records.")
    def classify_historical_cmd(dry_run, force):
        """Classify historical attendance records by original role context (GENERAL / SUBJECT / LEGACY)."""
        from app.attendance.classifier import run_historical_classification_migration
        click.echo(f"Starting historical attendance classification (dry_run={dry_run}, force={force})...")
        res = run_historical_classification_migration(dry_run=dry_run, force=force)
        click.echo(
            f"✓ Completed! Total: {res['total_after']} | GENERAL: {res['general_count']} | "
            f"SUBJECT: {res['subject_count']} | LEGACY: {res['legacy_count']} | Reclassified: {res['reclassified_count']}"
        )

    # Cache control for brand assets so updates reflect immediately
    @app.after_request
    def add_header(response):
        if request.path.startswith('/static/images/'):
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

    return app

def _auto_bootstrap_database(app):
    with app.app_context():
        try:
            from app.models.audit import AuditLog
            from app.models.attendance import Attendance
            from app.models.user import User
            from app.models.department import Department
            from app.models.student import Student
            from app.models.teacher import Teacher
            from app.models.settings import SystemSetting
            from app.models.session import AcademicSession
            from app.models.subject import Subject, teacher_subjects
            from app.models.subject_assignment import TeacherSubjectAssignment
            from app.models.class_coordinator import ClassCoordinator
            from sqlalchemy import inspect, text

            db.create_all()

            # Ensure attendances table has subject_id, teacher_id, semester, section, attendance_type columns
            # AND enforce composite uniqueness on (student_id, date, subject_id)
            try:
                inspector = inspect(db.engine)
                if 'attendances' in inspector.get_table_names():
                    cols = [c['name'] for c in inspector.get_columns('attendances')]
                    if 'subject_id' not in cols:
                        try:
                            db.session.execute(text("ALTER TABLE attendances ADD COLUMN subject_id INTEGER REFERENCES subjects(id)"))
                            db.session.commit()
                        except Exception as e:
                            db.session.rollback()
                    if 'teacher_id' not in cols:
                        try:
                            db.session.execute(text("ALTER TABLE attendances ADD COLUMN teacher_id INTEGER REFERENCES teachers(id)"))
                            db.session.commit()
                        except Exception as e:
                            db.session.rollback()
                    if 'semester' not in cols:
                        try:
                            db.session.execute(text("ALTER TABLE attendances ADD COLUMN semester VARCHAR(32)"))
                            db.session.commit()
                        except Exception as e:
                            db.session.rollback()
                    if 'section' not in cols:
                        try:
                            db.session.execute(text("ALTER TABLE attendances ADD COLUMN section VARCHAR(32)"))
                            db.session.commit()
                        except Exception as e:
                            db.session.rollback()
                    if 'attendance_type' not in cols:
                        try:
                            db.session.execute(text("ALTER TABLE attendances ADD COLUMN attendance_type VARCHAR(20) DEFAULT 'SUBJECT' NOT NULL"))
                            db.session.commit()
                        except Exception as e:
                            db.session.rollback()
                        # Backfill legacy attendance records safely
                        try:
                            db.session.execute(text("UPDATE attendances SET attendance_type = 'GENERAL' WHERE subject_id IS NULL"))
                            db.session.execute(text("UPDATE attendances SET attendance_type = 'SUBJECT' WHERE subject_id IS NOT NULL"))
                            db.session.commit()
                        except Exception as e:
                            db.session.rollback()

                    if 'classification_reason' not in cols:
                        try:
                            db.session.execute(text("ALTER TABLE attendances ADD COLUMN classification_reason VARCHAR(255)"))
                            db.session.commit()
                        except Exception as e:
                            db.session.rollback()

                    if 'classified_at' not in cols:
                        try:
                            db.session.execute(text("ALTER TABLE attendances ADD COLUMN classified_at DATETIME"))
                            db.session.commit()
                        except Exception as e:
                            db.session.rollback()

                if 'class_coordinators' in inspector.get_table_names():
                    coord_cols = [c['name'] for c in inspector.get_columns('class_coordinators')]
                    if 'effective_from' not in coord_cols:
                        try:
                            db.session.execute(text("ALTER TABLE class_coordinators ADD COLUMN effective_from DATE"))
                            db.session.commit()
                        except Exception as e:
                            db.session.rollback()
                    if 'effective_to' not in coord_cols:
                        try:
                            db.session.execute(text("ALTER TABLE class_coordinators ADD COLUMN effective_to DATE"))
                            db.session.commit()
                        except Exception as e:
                            db.session.rollback()

                    # Migrate UNIQUE constraint to include subject_id
                    dialect_name = db.engine.dialect.name
                    if dialect_name == 'sqlite':
                        res = db.session.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='attendances'")).fetchone()
                        table_sql = res[0] if res else ""
                        if 'UNIQUE (student_id, date)' in table_sql or 'uq_student_date_attendance' in table_sql:
                            app.logger.info("Migrating SQLite attendances table to support subject-wise attendance uniqueness...")
                            raw_conn = db.engine.raw_connection()
                            try:
                                cur = raw_conn.cursor()
                                cur.execute("PRAGMA foreign_keys = OFF")
                                cur.execute("BEGIN TRANSACTION")
                                cur.execute("""
                                CREATE TABLE attendances_migrated (
                                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                                    student_id INTEGER NOT NULL,
                                    subject_id INTEGER,
                                    teacher_id INTEGER,
                                    semester VARCHAR(32),
                                    section VARCHAR(32),
                                    date DATE NOT NULL,
                                    time_in TIME,
                                    time_out TIME,
                                    status VARCHAR(20) NOT NULL DEFAULT 'Present',
                                    marked_by INTEGER,
                                    method VARCHAR(20) NOT NULL DEFAULT 'QR',
                                    remarks VARCHAR(255),
                                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                                    CONSTRAINT uq_student_date_subject_attendance UNIQUE (student_id, date, subject_id),
                                    FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE CASCADE,
                                    FOREIGN KEY(subject_id) REFERENCES subjects (id) ON DELETE SET NULL,
                                    FOREIGN KEY(teacher_id) REFERENCES teachers (id) ON DELETE SET NULL,
                                    FOREIGN KEY(marked_by) REFERENCES users (id) ON DELETE SET NULL
                                )
                                """)
                                cur.execute("""
                                INSERT INTO attendances_migrated (id, student_id, subject_id, teacher_id, semester, section, date, time_in, time_out, status, marked_by, method, remarks, created_at, updated_at)
                                SELECT id, student_id, subject_id, teacher_id, semester, section, date, time_in, time_out, status, marked_by, method, remarks, created_at, updated_at
                                FROM attendances
                                """)
                                cur.execute("DROP TABLE attendances")
                                cur.execute("ALTER TABLE attendances_migrated RENAME TO attendances")
                                cur.execute("CREATE INDEX IF NOT EXISTS ix_attendances_date ON attendances (date)")
                                cur.execute("CREATE INDEX IF NOT EXISTS ix_attendances_student_id ON attendances (student_id)")
                                cur.execute("CREATE INDEX IF NOT EXISTS ix_attendances_subject_id ON attendances (subject_id)")
                                cur.execute("CREATE INDEX IF NOT EXISTS idx_attendance_date_student_subject ON attendances (date, student_id, subject_id)")
                                raw_conn.commit()
                                cur.execute("PRAGMA foreign_keys = ON")
                                app.logger.info("✓ SQLite attendances migration completed successfully.")
                            finally:
                                raw_conn.close()
                    elif dialect_name == 'postgresql':
                        try:
                            db.session.execute(text("ALTER TABLE attendances DROP CONSTRAINT IF EXISTS uq_student_date_attendance"))
                            db.session.execute(text("ALTER TABLE attendances DROP CONSTRAINT IF EXISTS uq_student_date"))
                            db.session.execute(text("ALTER TABLE attendances DROP CONSTRAINT IF EXISTS uq_attendances_student_date"))
                            db.session.execute(text("""
                                DO $$
                                BEGIN
                                    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_student_date_subject_attendance') THEN
                                        ALTER TABLE attendances ADD CONSTRAINT uq_student_date_subject_attendance UNIQUE (student_id, date, subject_id);
                                    END IF;
                                END $$;
                            """))
                            db.session.commit()
                        except Exception as pge:
                            db.session.rollback()
                            app.logger.warning(f"PostgreSQL attendances constraint migration notice: {pge}")
            except Exception as e:
                db.session.rollback()
                app.logger.warning(f"Attendance table inspection/alter skipped: {e}")

            from datetime import date

            # 1. System Settings
            settings_data = [
                ('institution_name', 'Dr. Virendra Swarup Memorial Trust Group of Institutions', 'Full legal institution name'),
                ('institution_email', 'contact@vsmt.edu.in', 'Official administrative contact email'),
                ('institution_phone', '+91 512-2580000', 'Institution contact telephone'),
                ('institution_address', 'Dr. Virendra Swarup Memorial Trust Group of Institutions, Kanpur-Lucknow National Highway, Unnao, UP', 'Physical campus address'),
                ('attendance_start_time', '08:00', 'Earliest permitted check-in time'),
                ('attendance_end_time', '18:00', 'Latest permitted check-out time'),
                ('duplicate_scan_cooldown_seconds', '60', 'Minimum seconds before accepting another scan for the same student')
            ]
            for key, val, desc in settings_data:
                existing_setting = SystemSetting.query.filter_by(key=key).first()
                if not existing_setting:
                    db.session.add(SystemSetting(key=key, value=val, description=desc))
                elif key == 'institution_name' and ('Apex' in (existing_setting.value or '') or 'Technology' in (existing_setting.value or '')):
                    existing_setting.value = val

            # 2. Academic Session
            if not AcademicSession.query.filter_by(name='2025-2026').first():
                db.session.add(AcademicSession(
                    name='2025-2026',
                    start_date=date(2025, 8, 1),
                    end_date=date(2026, 6, 30),
                    is_active=True
                ))

            # 3. Departments
            departments_data = [
                ('Computer Science & Engineering', 'CSE', 'Department of Computer Science and Software Engineering'),
                ('Electronics & Communication', 'ECE', 'Department of Electronics and Communications Engineering'),
                ('Mechanical Engineering', 'MECH', 'Department of Mechanical Engineering & Robotics'),
                ('Business Administration', 'BBA', 'Department of Management and Business Studies')
            ]
            depts = {}
            for name, code, desc in departments_data:
                dept = Department.query.filter_by(code=code).first()
                if not dept:
                    dept = Department(name=name, code=code, description=desc)
                    db.session.add(dept)
                    db.session.flush()
                depts[code] = dept

            # 4. Admin User
            admin = User.query.filter_by(username='admin').first()
            if not admin:
                admin = User(username='admin', email='admin@vsmt.edu.in', role='admin', is_active=True)
                admin.set_password('Admin@1234')
                db.session.add(admin)
                app.logger.info("Auto-bootstrap: Created admin user.")

            # 5. Teacher User
            teacher_user = User.query.filter_by(username='teacher').first()
            if not teacher_user:
                teacher_user = User(username='teacher', email='teacher@vsmt.edu.in', role='teacher', is_active=True)
                teacher_user.set_password('Teacher@1234')
                db.session.add(teacher_user)
                db.session.flush()

                cse = depts.get('CSE') or Department.query.filter_by(code='CSE').first()
                if cse:
                    teacher_profile = Teacher(
                        user_id=teacher_user.id,
                        employee_id='TCH101',
                        full_name='Dr. Alan Turing',
                        email='teacher@vsmt.edu.in',
                        phone='+1-555-0101',
                        department_id=cse.id,
                        designation='Associate Professor'
                    )
                    db.session.add(teacher_profile)
                app.logger.info("Auto-bootstrap: Created teacher user.")

            # 6. Student User
            student_user = User.query.filter_by(username='student').first()
            if not student_user:
                student_user = User(username='student', email='student@vsmt.edu.in', role='student', is_active=True)
                student_user.set_password('Student@1234')
                db.session.add(student_user)
                db.session.flush()

                cse = depts.get('CSE') or Department.query.filter_by(code='CSE').first()
                if cse:
                    student_profile = Student(
                        user_id=student_user.id,
                        student_id='STU2026001',
                        full_name='Alex Johnson',
                        father_name='Robert Johnson',
                        mother_name='Mary Johnson',
                        email='student@vsmt.edu.in',
                        phone='+1-555-0202',
                        date_of_birth=date(2004, 5, 14),
                        gender='Male',
                        department_id=cse.id,
                        course='B.Tech Computer Science',
                        semester='4th',
                        section='A',
                        roll_number='CS-2024-042',
                        address='42 Innovation Drive, Tech City',
                        qr_token=Student.generate_qr_token(),
                        admission_date=date(2024, 8, 1),
                        is_active=True
                    )
                    db.session.add(student_profile)
                app.logger.info("Auto-bootstrap: Created student user.")

            # 7. Default Subjects
            cse = depts.get('CSE') or Department.query.filter_by(code='CSE').first()
            if cse:
                sample_subjects = [
                    ('CS101', 'Data Structures', 'Fundamental data structures, trees, graphs, and algorithmic complexity.', '4th'),
                    ('CS102', 'Database Management System', 'Relational database design, SQL, normalization, transactions, and indexing.', '4th'),
                    ('CS103', 'Web Technology', 'Modern web architecture, REST APIs, client-server models, and security.', '4th'),
                    ('CS104', 'Software Engineering', 'Software development lifecycle, agile methodologies, and QA testing.', '4th'),
                    ('CS105', 'Operating System', 'Processes, memory virtualization, concurrency, and file systems.', '4th'),
                ]
                teacher_obj = Teacher.query.filter_by(employee_id='TCH101').first()
                for scode, sname, sdesc, sem in sample_subjects:
                    sub = Subject.query.filter_by(subject_code=scode).first()
                    if not sub:
                        sub = Subject(
                            subject_code=scode,
                            subject_name=sname,
                            description=sdesc,
                            department_id=cse.id,
                            course='B.Tech Computer Science',
                            semester=sem,
                            is_active=True
                        )
                        db.session.add(sub)
                        db.session.flush()

                    if teacher_obj:
                        if teacher_obj not in sub.teachers:
                            sub.teachers.append(teacher_obj)
                        
                        # Also ensure formal TeacherSubjectAssignment exists
                        existing_assign = TeacherSubjectAssignment.query.filter_by(
                            teacher_id=teacher_obj.id,
                            subject_id=sub.id,
                            semester=sub.semester or '4th'
                        ).first()
                        if not existing_assign:
                            new_assign = TeacherSubjectAssignment(
                                teacher_id=teacher_obj.id,
                                subject_id=sub.id,
                                semester=sub.semester or '4th',
                                department_id=sub.department_id,
                                course=sub.course,
                                is_active=True
                            )
                            db.session.add(new_assign)
                            app.logger.info(f"Auto-bootstrap: Assigned {scode} to {teacher_obj.full_name} for {sub.semester} Semester")

            # Idempotent historical attendance classification
            try:
                from app.attendance.classifier import run_historical_classification_migration
                run_historical_classification_migration(dry_run=False)
            except Exception as hce:
                app.logger.warning(f"Historical attendance classification bootstrap notice: {hce}")

            db.session.commit()
            app.logger.info("✓ Database auto-bootstrap completed.")
        except Exception as e:
            db.session.rollback()
            app.logger.warning(f"Database auto-bootstrap skipped: {e}")

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

    @app.errorhandler(413)
    def request_entity_too_large(e):
        return make_error_response(413, 'File Too Large', 'The uploaded file exceeds the maximum allowed size (5MB). Please select a smaller photo.')

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        app.logger.error(f"500 Internal Server Error: {e}", exc_info=True)
        return make_error_response(500, 'Server Error', 'An unexpected internal server error occurred. Please try again or check the details.')

