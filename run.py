import os
from datetime import datetime, date, timedelta
import click
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.department import Department
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.attendance import Attendance
from app.models.holiday import Holiday
from app.models.session import AcademicSession
from app.models.settings import SystemSetting
from app.models.audit import AuditLog

app = create_app(os.environ.get('FLASK_ENV', 'development'))

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'Department': Department,
        'Student': Student,
        'Teacher': Teacher,
        'Attendance': Attendance,
        'Holiday': Holiday,
        'AcademicSession': AcademicSession,
        'SystemSetting': SystemSetting,
        'AuditLog': AuditLog
    }

@app.cli.command('init-db')
def init_db_command():
    """Create all database tables."""
    db.create_all()
    click.echo("✓ Database tables created successfully.")

@app.cli.command('seed')
def seed_command():
    """Seed initial development data: Admin, Teacher, Student, Departments, Session, Settings."""
    db.create_all()
    
    # 1. System Settings
    settings_data = [
        ('institution_name', 'Apex Institute of Technology & Management', 'Full legal institution name'),
        ('institution_email', 'contact@apex-institute.edu', 'Official administrative contact email'),
        ('institution_phone', '+1-555-0199', 'Institution contact telephone'),
        ('institution_address', '100 Academic Way, Tech Corridor, Metro City', 'Physical campus address'),
        ('attendance_start_time', '08:00', 'Earliest permitted check-in time'),
        ('attendance_end_time', '18:00', 'Latest permitted check-out time'),
        ('duplicate_scan_cooldown_seconds', '60', 'Minimum seconds before accepting another scan for the same student')
    ]
    for key, val, desc in settings_data:
        if not SystemSetting.query.filter_by(key=key).first():
            db.session.add(SystemSetting(key=key, value=val, description=desc))
    
    # 2. Academic Session
    session = AcademicSession.query.filter_by(name='2025-2026').first()
    if not session:
        session = AcademicSession(
            name='2025-2026',
            start_date=date(2025, 8, 1),
            end_date=date(2026, 6, 30),
            is_active=True
        )
        db.session.add(session)
    
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
        
    # 4. Holidays
    sample_holidays = [
        ('Republic Day', date(2026, 1, 26), 'National holiday celebration'),
        ('Independence Day', date(2026, 8, 15), 'National holiday celebration'),
        ('Labor Day', date(2026, 5, 1), 'International Workers Day')
    ]
    for title, hdate, desc in sample_holidays:
        if not Holiday.query.filter_by(date=hdate).first():
            db.session.add(Holiday(title=title, date=hdate, description=desc))

    # 5. Default Users (Admin, Teacher, Student)
    # Admin
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        admin_user = User(
            username='admin',
            email='admin@erp.local',
            role='admin',
            is_active=True
        )
        admin_user.set_password('Admin@1234')
        db.session.add(admin_user)
        click.echo("✓ Created Admin: admin / Admin@1234")

    # Teacher
    teacher_user = User.query.filter_by(username='teacher').first()
    if not teacher_user:
        teacher_user = User(
            username='teacher',
            email='teacher@erp.local',
            role='teacher',
            is_active=True
        )
        teacher_user.set_password('Teacher@1234')
        db.session.add(teacher_user)
        db.session.flush()

        teacher_profile = Teacher(
            user_id=teacher_user.id,
            employee_id='TCH101',
            full_name='Dr. Alan Turing',
            email='teacher@erp.local',
            phone='+1-555-0101',
            department_id=depts['CSE'].id,
            designation='Associate Professor'
        )
        db.session.add(teacher_profile)
        click.echo("✓ Created Teacher: teacher / Teacher@1234 (Dr. Alan Turing)")

    # Student
    student_user = User.query.filter_by(username='student').first()
    if not student_user:
        student_user = User(
            username='student',
            email='student@erp.local',
            role='student',
            is_active=True
        )
        student_user.set_password('Student@1234')
        db.session.add(student_user)
        db.session.flush()

        student_profile = Student(
            user_id=student_user.id,
            student_id='STU2026001',
            full_name='Alex Johnson',
            father_name='Robert Johnson',
            mother_name='Mary Johnson',
            email='student@erp.local',
            phone='+1-555-0202',
            date_of_birth=date(2004, 5, 14),
            gender='Male',
            department_id=depts['CSE'].id,
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
        click.echo("✓ Created Student: student / Student@1234 (Alex Johnson)")

    # Add 2 more sample students for realistic testing
    sample_students = [
        ('STU2026002', 'Sophia Chen', 'Chen Wei', 'Lin Chen', 'sophia.chen@erp.local', 'Female', 'CSE', 'CS-2024-043'),
        ('STU2026003', 'Marcus Aurelius', 'Severus', 'Julia', 'marcus.a@erp.local', 'Male', 'ECE', 'EC-2024-012')
    ]
    for sid, name, fname, mname, email, gender, dept_code, roll in sample_students:
        if not Student.query.filter_by(student_id=sid).first():
            stu = Student(
                student_id=sid,
                full_name=name,
                father_name=fname,
                mother_name=mname,
                email=email,
                phone='+1-555-0303',
                date_of_birth=date(2004, 9, 20),
                gender=gender,
                department_id=depts[dept_code].id,
                course='B.Tech ' + depts[dept_code].name,
                semester='4th',
                section='A',
                roll_number=roll,
                qr_token=Student.generate_qr_token(),
                admission_date=date(2024, 8, 1),
                is_active=True
            )
            db.session.add(stu)

    db.session.commit()
    click.echo("✓ Database seeded successfully with demo records.")

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        app.cli()
    else:
        port = int(os.environ.get('PORT', 5001))
        app.run(host='0.0.0.0', port=port, debug=app.config.get('DEBUG', True))

