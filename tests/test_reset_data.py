import pytest
from datetime import date, datetime
from app.extensions import db
from app.models.user import User
from app.models.department import Department
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.subject import Subject
from app.models.subject_assignment import TeacherSubjectAssignment
from app.models.class_coordinator import ClassCoordinator
from app.models.attendance import Attendance
from app.models.session import AcademicSession
from app.models.audit import AuditLog
from app.utils.reset_service import (
    get_reset_preview,
    create_reset_snapshot,
    execute_reset,
    MODE_ATTENDANCE,
    MODE_OPERATIONAL,
    MODE_FACTORY,
)


@pytest.fixture
def seed_test_erp_data(app):
    """Seed sample data across all operational and master tables."""
    with app.app_context():
        # Department
        dept = Department.query.filter_by(code='TCSE').first()
        if not dept:
            dept = Department(name='Test CSE', code='TCSE', description='Test Department')
            db.session.add(dept)
            db.session.flush()

        # Session
        sess = AcademicSession.query.filter_by(name='2025-2026').first()
        if not sess:
            sess = AcademicSession(name='2025-2026', start_date=date(2025, 8, 1), end_date=date(2026, 6, 30), is_active=True)
            db.session.add(sess)
            db.session.flush()

        # Admin
        admin = User.query.filter_by(username='test_admin').first()
        if not admin:
            admin = User(username='test_admin', email='admin@test.com', role='admin', is_active=True)
            admin.set_password('AdminSecret@123')
            db.session.add(admin)
            db.session.flush()
        else:
            admin.set_password('AdminSecret@123')
            admin.is_active = True
            admin.role = 'admin'

        # Teacher
        t_user = User.query.filter_by(username='test_teacher').first()
        if not t_user:
            t_user = User(username='test_teacher', email='teacher@test.com', role='teacher', is_active=True)
            t_user.set_password('TeacherSecret@123')
            db.session.add(t_user)
            db.session.flush()
        else:
            t_user.set_password('TeacherSecret@123')
            t_user.is_active = True
            t_user.role = 'teacher'

        teacher = Teacher.query.filter_by(user_id=t_user.id).first()
        if not teacher:
            teacher = Teacher(
                user_id=t_user.id,
                employee_id='TCH999',
                full_name='Prof. Test Teacher',
                email='teacher@test.com',
                department_id=dept.id,
                designation='Assistant Professor'
            )
            db.session.add(teacher)
            db.session.flush()

        # Subject
        sub = Subject.query.filter_by(subject_code='TSUB101').first()
        if not sub:
            sub = Subject(
                subject_code='TSUB101',
                subject_name='Test Subject 101',
                department_id=dept.id,
                course='B.Tech',
                semester='4th Semester',
                session_id=sess.id,
                is_active=True
            )
            db.session.add(sub)
            db.session.flush()

        # Assignment
        asgn = TeacherSubjectAssignment.query.filter_by(teacher_id=teacher.id, subject_id=sub.id).first()
        if not asgn:
            asgn = TeacherSubjectAssignment(
                teacher_id=teacher.id,
                subject_id=sub.id,
                department_id=dept.id,
                session_id=sess.id,
                semester='4th Semester',
                section='A'
            )
            db.session.add(asgn)
            db.session.flush()

        # Student
        s_user = User.query.filter_by(username='test_student').first()
        if not s_user:
            s_user = User(username='test_student', email='student@test.com', role='student', is_active=True)
            s_user.set_password('StudentSecret@123')
            db.session.add(s_user)
            db.session.flush()
        else:
            s_user.set_password('StudentSecret@123')
            s_user.is_active = True
            s_user.role = 'student'

        student = Student.query.filter_by(user_id=s_user.id).first()
        if not student:
            student = Student(
                user_id=s_user.id,
                student_id='STUTEST001',
                full_name='Test Student One',
                email='student@test.com',
                department_id=dept.id,
                course='B.Tech',
                semester='4th Semester',
                section='A',
                roll_number='ROLL-999',
                qr_token=Student.generate_qr_token(),
                is_active=True
            )
            db.session.add(student)
            db.session.flush()

        # Attendance Record
        att = Attendance.query.filter_by(student_id=student.id, subject_id=sub.id).first()
        if not att:
            att = Attendance(
                student_id=student.id,
                subject_id=sub.id,
                teacher_id=teacher.id,
                semester='4th Semester',
                section='A',
                date=date.today(),
                status='Present',
                attendance_type='SUBJECT',
                method='Manual'
            )
            db.session.add(att)

        db.session.commit()
        return {'admin': admin, 'teacher': teacher, 'student': student, 'subject': sub}


def test_get_reset_preview_and_snapshot(app, seed_test_erp_data):
    """Test preview counts and snapshot creation."""
    with app.app_context():
        admin = User.query.filter_by(username='test_admin').first()
        preview_att = get_reset_preview(MODE_ATTENDANCE)
        assert preview_att['reset_type'] == 'ATTENDANCE'
        assert preview_att['attendance_count'] >= 1
        assert preview_att['requires_password'] is False

        preview_op = get_reset_preview(MODE_OPERATIONAL)
        assert preview_op['reset_type'] == 'OPERATIONAL'
        assert preview_op['students_count'] >= 1
        assert preview_op['teachers_count'] >= 1
        assert preview_op['requires_password'] is True

        snapshot_path = create_reset_snapshot(MODE_ATTENDANCE, admin)
        assert 'reset_snapshot_attendance' in snapshot_path


def test_reset_attendance_data(app, seed_test_erp_data):
    """Mode 1: Reset Attendance Data clears attendance while keeping roster intact."""
    with app.app_context():
        admin = User.query.filter_by(username='test_admin').first()
        assert Attendance.query.count() >= 1
        assert Student.query.count() >= 1
        assert Teacher.query.count() >= 1

        success, counts, msg = execute_reset(MODE_ATTENDANCE, admin)
        assert success is True
        assert counts.get('attendances', 0) >= 1

        # Assert post-condition
        assert Attendance.query.count() == 0
        assert Student.query.count() >= 1
        assert Teacher.query.count() >= 1
        assert Subject.query.count() >= 1
        assert User.query.filter_by(username='test_admin').first() is not None


def test_reset_operational_erp_data(app, seed_test_erp_data):
    """Mode 2: Reset Operational Data clears students, teachers, assignments, leaves master subjects."""
    with app.app_context():
        admin = User.query.filter_by(username='test_admin').first()

        success, counts, msg = execute_reset(MODE_OPERATIONAL, admin)
        assert success is True
        assert Attendance.query.count() == 0
        assert Student.query.count() == 0
        assert Teacher.query.count() == 0
        assert TeacherSubjectAssignment.query.count() == 0

        # Master subjects, academic sessions, and Admin are preserved
        assert Subject.query.count() >= 1
        assert AcademicSession.query.count() >= 1
        refreshed_admin = User.query.filter_by(username='test_admin').first()
        assert refreshed_admin is not None
        assert refreshed_admin.is_active is True


def test_full_factory_reset(app, seed_test_erp_data):
    """Mode 3: Full Factory Reset clears operational and master subjects, restores default session."""
    with app.app_context():
        admin = User.query.filter_by(username='test_admin').first()

        success, counts, msg = execute_reset(MODE_FACTORY, admin)
        assert success is True
        assert Attendance.query.count() == 0
        assert Student.query.count() == 0
        assert Teacher.query.count() == 0
        assert Subject.query.count() == 0

        # Super Admin is preserved or restored
        assert User.query.filter_by(role='admin').count() >= 1
        assert AcademicSession.query.filter_by(is_active=True).first() is not None


def test_reset_endpoints_security_and_authorization(client, app, seed_test_erp_data):
    """Test API & Web authorization: non-admin rejected, password verification, typed confirmation."""
    with app.app_context():
        admin = User.query.filter_by(username='test_admin').first()
        teacher_user = User.query.filter_by(username='test_teacher').first()

    # 1. Non-admin access rejected
    client.post('/auth/login', data={'identity': 'test_teacher', 'password': 'TeacherSecret@123'})

    res = client.get('/admin/settings/reset/preview')
    assert res.status_code in (403, 302)

    api_res = client.get('/api/admin/reset/preview')
    assert api_res.status_code == 403

    client.get('/auth/logout')

    # 2. Admin access without correct confirmation string
    client.post('/auth/login', data={'identity': 'test_admin', 'password': 'AdminSecret@123'})

    # Bad confirmation
    bad_res = client.post('/api/admin/reset', json={
        'reset_type': 'ATTENDANCE',
        'confirmation_text': 'WRONG TEXT'
    })
    assert bad_res.status_code == 400
    assert "RESET DATA" in bad_res.json['message']

    # Operational reset with wrong password
    bad_pwd_res = client.post('/api/admin/reset', json={
        'reset_type': 'OPERATIONAL',
        'confirmation_text': 'RESET DATA',
        'admin_password': 'WrongPassword123'
    })
    assert bad_pwd_res.status_code == 403
    assert "password" in bad_pwd_res.json['message'].lower()

    # Operational reset with correct password succeeds
    good_res = client.post('/api/admin/reset', json={
        'reset_type': 'ATTENDANCE',
        'confirmation_text': 'RESET DATA'
    })
    assert good_res.status_code == 200
    assert good_res.json['success'] is True
