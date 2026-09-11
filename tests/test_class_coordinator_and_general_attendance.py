import pytest
from datetime import date, datetime
from app.extensions import db
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.user import User
from app.models.department import Department
from app.models.subject import Subject
from app.models.subject_assignment import TeacherSubjectAssignment
from app.models.class_coordinator import ClassCoordinator
from app.models.attendance import Attendance
from app.attendance.services import process_qr_attendance


@pytest.fixture
def setup_coordinator_environment(app):
    """
    Setup clean database state for coordinator and attendance separation tests.
    Creates:
    - 1 Department: Computer Science (CSE)
    - 2 Teachers: Dr. Amit Kumar (emp001), Dr. Neha Sharma (emp002)
    - 5 Subjects: DBMS, DS, OS, WebTech, SE
    - 2 Students: Rahul Sharma (CSE 4th A), Priya Patel (CSE 4th B)
    """
    with app.app_context():
        # Clean existing test data
        Attendance.query.delete()
        ClassCoordinator.query.delete()
        TeacherSubjectAssignment.query.delete()
        Student.query.delete()
        Teacher.query.delete()
        Subject.query.delete()
        Department.query.delete()
        User.query.filter(User.username.in_(['amit', 'neha', 'rahul', 'priya', 'admin'])).delete()
        db.session.commit()

        # Department
        dept = Department(name="Computer Science & Engineering", code="CSE")
        db.session.add(dept)
        db.session.commit()

        # Teacher Users & Profiles
        u_amit = User(username='amit', email='amit@test.edu', role='teacher', is_active=True)
        u_amit.set_password('pass123')
        db.session.add(u_amit)
        db.session.commit()

        t_amit = Teacher(user_id=u_amit.id, employee_id="EMP001", full_name="Dr. Amit Kumar", email=u_amit.email, department_id=dept.id, is_active=True)
        db.session.add(t_amit)

        u_neha = User(username='neha', email='neha@test.edu', role='teacher', is_active=True)
        u_neha.set_password('pass123')
        db.session.add(u_neha)
        db.session.commit()

        t_neha = Teacher(user_id=u_neha.id, employee_id="EMP002", full_name="Dr. Neha Sharma", email=u_neha.email, department_id=dept.id, is_active=True)
        db.session.add(t_neha)
        db.session.commit()

        # Students
        u_rahul = User(username='rahul', email='rahul@test.edu', role='student', is_active=True)
        u_rahul.set_password('pass123')
        db.session.add(u_rahul)
        db.session.commit()

        s_rahul = Student(
            user_id=u_rahul.id,
            student_id="STU2026001",
            roll_number="CSE-4A-01",
            full_name="Rahul Sharma",
            course="B.Tech",
            department_id=dept.id,
            semester="4th Semester",
            section="A",
            qr_token="TOKEN_RAHUL_CSE4A",
            is_active=True
        )
        db.session.add(s_rahul)

        u_priya = User(username='priya', email='priya@test.edu', role='student', is_active=True)
        u_priya.set_password('pass123')
        db.session.add(u_priya)
        db.session.commit()

        s_priya = Student(
            user_id=u_priya.id,
            student_id="STU2026002",
            roll_number="CSE-4B-01",
            full_name="Priya Patel",
            course="B.Tech",
            department_id=dept.id,
            semester="4th Semester",
            section="B",
            qr_token="TOKEN_PRIYA_CSE4B",
            is_active=True
        )
        db.session.add(s_priya)

        # 5 Subjects
        sub_dbms = Subject(subject_code="CS401", subject_name="Database Management Systems", semester="4th Semester", department_id=dept.id, is_active=True)
        sub_ds = Subject(subject_code="CS402", subject_name="Data Structures", semester="4th Semester", department_id=dept.id, is_active=True)
        sub_os = Subject(subject_code="CS403", subject_name="Operating System", semester="4th Semester", department_id=dept.id, is_active=True)
        sub_wt = Subject(subject_code="CS404", subject_name="Web Technology", semester="4th Semester", department_id=dept.id, is_active=True)
        sub_se = Subject(subject_code="CS405", subject_name="Software Engineering", semester="4th Semester", department_id=dept.id, is_active=True)
        db.session.add_all([sub_dbms, sub_ds, sub_os, sub_wt, sub_se])
        db.session.commit()

        # Subject assignments to Dr. Amit
        asgn_dbms = TeacherSubjectAssignment(teacher_id=t_amit.id, subject_id=sub_dbms.id, semester="4th Semester", section="A", is_active=True)
        asgn_ds = TeacherSubjectAssignment(teacher_id=t_amit.id, subject_id=sub_ds.id, semester="4th Semester", section="A", is_active=True)
        asgn_os = TeacherSubjectAssignment(teacher_id=t_amit.id, subject_id=sub_os.id, semester="4th Semester", section="A", is_active=True)
        asgn_wt = TeacherSubjectAssignment(teacher_id=t_amit.id, subject_id=sub_wt.id, semester="4th Semester", section="A", is_active=True)
        asgn_se = TeacherSubjectAssignment(teacher_id=t_amit.id, subject_id=sub_se.id, semester="4th Semester", section="A", is_active=True)
        db.session.add_all([asgn_dbms, asgn_ds, asgn_os, asgn_wt, asgn_se])

        # Dr. Amit is assigned as Class Coordinator for B.Tech CSE 4th Semester Section A
        coord_amit = ClassCoordinator.assign_coordinator(
            teacher_id=t_amit.id,
            department_id=dept.id,
            course="B.Tech",
            semester="4th Semester",
            section="A",
            is_active=True
        )

        db.session.commit()

        yield {
            'dept': dept,
            'teacher_amit': t_amit,
            'teacher_neha': t_neha,
            'student_rahul': s_rahul,
            'student_priya': s_priya,
            'sub_dbms': sub_dbms,
            'sub_ds': sub_ds,
            'sub_os': sub_os,
            'sub_wt': sub_wt,
            'sub_se': sub_se,
            'coord_amit': coord_amit
        }


def test_class_coordinator_assignment_and_uniqueness(app, setup_coordinator_environment):
    """Test assigning Class Coordinator, uniqueness per class, and auto-deactivation of prior coordinator."""
    with app.app_context():
        env = setup_coordinator_environment
        t_amit = env['teacher_amit']
        t_neha = env['teacher_neha']
        dept = env['dept']

        # Dr. Amit is currently active coordinator for CSE 4th A
        active_coords = ClassCoordinator.query.filter_by(semester="4th Semester", section="A", is_active=True).all()
        assert len(active_coords) == 1
        assert active_coords[0].teacher_id == t_amit.id

        # Reassign CSE 4th A to Dr. Neha
        new_coord = ClassCoordinator.assign_coordinator(
            teacher_id=t_neha.id,
            department_id=dept.id,
            course="B.Tech",
            semester="4th Semester",
            section="A",
            is_active=True
        )

        # Check that old coordinator (Dr. Amit) was automatically deactivated
        active_now = ClassCoordinator.query.filter_by(semester="4th Semester", section="A", is_active=True).all()
        assert len(active_now) == 1
        assert active_now[0].teacher_id == t_neha.id
        assert active_now[0].id == new_coord.id

        old_amit_coord = ClassCoordinator.query.filter_by(teacher_id=t_amit.id, semester="4th Semester", section="A").first()
        assert old_amit_coord.is_active is False


def test_coordinator_authorization_scope(app, setup_coordinator_environment):
    """Test that coordinator can take general attendance for assigned class, but NOT for other classes."""
    with app.app_context():
        env = setup_coordinator_environment
        t_amit = env['teacher_amit']
        t_neha = env['teacher_neha']
        s_rahul = env['student_rahul']  # CSE 4th Section A
        s_priya = env['student_priya']  # CSE 4th Section B

        today = date.today()

        # Dr. Amit is coordinator for Section A.
        # He scans Rahul (Section A) -> should succeed
        res_rahul = process_qr_attendance(
            token=s_rahul.qr_token,
            teacher=t_amit,
            attendance_type='GENERAL',
            att_date=today
        )
        assert res_rahul['success'] is True
        assert res_rahul['attendance_type'] == 'GENERAL'
        assert res_rahul['action'] == 'TIME_IN'

        # Dr. Amit scans Priya (Section B) -> Should be rejected with UNAUTHORIZED_COORDINATOR
        res_priya = process_qr_attendance(
            token=s_priya.qr_token,
            teacher=t_amit,
            attendance_type='GENERAL',
            att_date=today
        )
        assert res_priya['success'] is False
        assert res_priya['action'] == 'UNAUTHORIZED_COORDINATOR'

        # Dr. Neha (not coordinator for Section A) tries to scan Rahul for General Attendance -> rejected
        res_neha_rahul = process_qr_attendance(
            token=s_rahul.qr_token,
            teacher=t_neha,
            attendance_type='GENERAL',
            att_date=today
        )
        assert res_neha_rahul['success'] is False
        assert res_neha_rahul['action'] == 'UNAUTHORIZED_COORDINATOR'


def test_five_subject_attendances_do_not_inflate_general_present_today(app, setup_coordinator_environment):
    """
    DEFINITIVE BUSINESS RULE TEST:
    1 Student marked Present in 5 subjects on the same day + 1 General Attendance.
    General Present Today MUST BE EXACTLY 1.
    Each subject must also show Present = 1 independently.
    """
    with app.app_context():
        env = setup_coordinator_environment
        t_amit = env['teacher_amit']
        s_rahul = env['student_rahul']
        today = date.today()

        # 1. Class Coordinator takes General Attendance for Rahul
        res_gen = process_qr_attendance(
            token=s_rahul.qr_token,
            teacher=t_amit,
            attendance_type='GENERAL',
            att_date=today
        )
        assert res_gen['success'] is True
        assert res_gen['attendance_type'] == 'GENERAL'

        # 2. Teachers take attendance in 5 distinct subjects for Rahul on the same date
        subjects = [env['sub_dbms'], env['sub_ds'], env['sub_os'], env['sub_wt'], env['sub_se']]
        for sub in subjects:
            res_sub = process_qr_attendance(
                token=s_rahul.qr_token,
                teacher=t_amit,
                subject_id=sub.id,
                semester="4th Semester",
                attendance_type='SUBJECT',
                att_date=today
            )
            assert res_sub['success'] is True
            assert res_sub['attendance_type'] == 'SUBJECT'
            assert res_sub['action'] == 'TIME_IN'

        # Total attendance rows in database for Rahul today = 6 (1 GENERAL + 5 SUBJECT)
        rahul_records = Attendance.query.filter_by(student_id=s_rahul.id, date=today).all()
        assert len(rahul_records) == 6
        assert sum(1 for r in rahul_records if r.attendance_type == 'GENERAL') == 1
        assert sum(1 for r in rahul_records if r.attendance_type == 'SUBJECT') == 5

        # 3. VERIFY DASHBOARD QUERY CALCULATION:
        # General Present Today strictly counts distinct students with attendance_type == 'GENERAL'
        from sqlalchemy import func
        gen_present_today = Attendance.query.filter(
            Attendance.date == today,
            Attendance.status.in_(['Present', 'Late', 'Half Day']),
            (Attendance.attendance_type == 'GENERAL') | (Attendance.subject_id.is_(None))
        ).with_entities(func.count(func.distinct(Attendance.student_id))).scalar() or 0

        # MUST BE EXACTLY 1, NOT 5, NOT 6!
        assert gen_present_today == 1

        # 4. VERIFY SUBJECT-WISE DASHBOARD COUNTS:
        # Each subject must independently count 1 present
        for sub in subjects:
            sub_count = Attendance.query.filter(
                Attendance.date == today,
                Attendance.subject_id == sub.id,
                Attendance.status.in_(['Present', 'Late', 'Half Day'])
            ).count()
            assert sub_count == 1

        # 5. VERIFY STUDENT OVERALL ATTENDANCE CALCULATION:
        # Student's daily general attendance percentage must NOT be inflated by 5 subject attendances
        stats = s_rahul.calculate_attendance_stats()
        # 1 day session conducted, 1 present -> 100%, total_sessions = 1
        assert stats['total_sessions'] == 1
        assert stats['present_count'] == 1
        assert stats['percentage'] == 100.0


def test_duplicate_prevention_independent_per_type_and_subject(app, setup_coordinator_environment):
    """
    Test that duplicate prevention works independently:
    - Scanning Rahul twice in GENERAL -> 1st TIME_IN, 2nd TIME_OUT / Completed.
    - Scanning Rahul in DBMS does NOT get blocked by General.
    - Scanning Rahul twice in DBMS -> 1st TIME_IN, 2nd TIME_OUT.
    - Scanning Rahul in Data Structures still succeeds.
    """
    with app.app_context():
        env = setup_coordinator_environment
        t_amit = env['teacher_amit']
        s_rahul = env['student_rahul']
        sub_dbms = env['sub_dbms']
        sub_ds = env['sub_ds']
        today = date.today()

        # General Scan 1: TIME_IN
        g1 = process_qr_attendance(token=s_rahul.qr_token, teacher=t_amit, attendance_type='GENERAL', att_date=today)
        assert g1['success'] is True
        assert g1['action'] == 'TIME_IN'

        # Fast-forward cooldown for General Attendance
        from datetime import datetime, timedelta
        rec_gen = Attendance.query.filter_by(student_id=s_rahul.id, date=today, attendance_type='GENERAL').first()
        rec_gen.time_in = (datetime.now() - timedelta(minutes=5)).time()
        db.session.commit()

        # General Scan 2: TIME_OUT
        g2 = process_qr_attendance(token=s_rahul.qr_token, teacher=t_amit, attendance_type='GENERAL', att_date=today)
        assert g2['success'] is True
        assert g2['action'] == 'TIME_OUT'

        # General Scan 3: ALREADY_COMPLETED
        g3 = process_qr_attendance(token=s_rahul.qr_token, teacher=t_amit, attendance_type='GENERAL', att_date=today)
        assert g3['success'] is False
        assert g3['action'] == 'ALREADY_COMPLETED'

        # Now DBMS scan 1 must still succeed! General being completed does NOT block DBMS.
        dbms1 = process_qr_attendance(token=s_rahul.qr_token, teacher=t_amit, subject_id=sub_dbms.id, semester="4th Semester", attendance_type='SUBJECT', att_date=today)
        assert dbms1['success'] is True
        assert dbms1['action'] == 'TIME_IN'
        assert dbms1['attendance_type'] == 'SUBJECT'

        # Fast-forward cooldown for DBMS
        rec_dbms = Attendance.query.filter_by(student_id=s_rahul.id, date=today, subject_id=sub_dbms.id, attendance_type='SUBJECT').first()
        rec_dbms.time_in = (datetime.now() - timedelta(minutes=5)).time()
        db.session.commit()

        # DBMS scan 2: TIME_OUT for DBMS
        dbms2 = process_qr_attendance(token=s_rahul.qr_token, teacher=t_amit, subject_id=sub_dbms.id, semester="4th Semester", attendance_type='SUBJECT', att_date=today)
        assert dbms2['success'] is True
        assert dbms2['action'] == 'TIME_OUT'

        # DBMS scan 3: ALREADY_COMPLETED for DBMS
        dbms3 = process_qr_attendance(token=s_rahul.qr_token, teacher=t_amit, subject_id=sub_dbms.id, semester="4th Semester", attendance_type='SUBJECT', att_date=today)
        assert dbms3['success'] is False
        assert dbms3['action'] == 'ALREADY_COMPLETED'

        # Data Structures scan 1 must STILL SUCCEED!
        ds1 = process_qr_attendance(token=s_rahul.qr_token, teacher=t_amit, subject_id=sub_ds.id, semester="4th Semester", attendance_type='SUBJECT', att_date=today)
        assert ds1['success'] is True
        assert ds1['action'] == 'TIME_IN'
        assert ds1['attendance_type'] == 'SUBJECT'


def test_api_scan_and_dashboard_stats(client, app, setup_coordinator_environment):
    """
    Test the REST API endpoints:
    - POST /api/attendance/scan with attendance_type='GENERAL'
    - POST /api/attendance/scan with attendance_type='SUBJECT'
    - GET /api/dashboard/stats returns present_today == 1 for 1 student with multiple subject scans
    """
    with app.app_context():
        env = setup_coordinator_environment
        t_amit = env['teacher_amit']
        s_rahul = env['student_rahul']
        sub_dbms = env['sub_dbms']
        sub_ds = env['sub_ds']

    # Login as teacher Dr. Amit
    client.post('/auth/login', data={'username': 'amit', 'password': 'pass123'}, follow_redirects=True)

    # 1. API Scan General
    res_gen = client.post('/api/attendance/scan', json={
        'token': s_rahul.qr_token,
        'attendance_type': 'GENERAL'
    })
    assert res_gen.status_code == 200
    data_gen = res_gen.get_json()
    assert data_gen['success'] is True
    assert data_gen['attendance_type'] == 'GENERAL'
    assert data_gen['action'] == 'TIME_IN'

    # 2. API Scan Subject DBMS
    res_sub1 = client.post('/api/attendance/scan', json={
        'token': s_rahul.qr_token,
        'attendance_type': 'SUBJECT',
        'subject_id': sub_dbms.id,
        'semester': '4th Semester'
    })
    assert res_sub1.status_code == 200
    data_sub1 = res_sub1.get_json()
    assert data_sub1['success'] is True
    assert data_sub1['attendance_type'] == 'SUBJECT'

    # 3. API Scan Subject Data Structures
    res_sub2 = client.post('/api/attendance/scan', json={
        'token': s_rahul.qr_token,
        'attendance_type': 'SUBJECT',
        'subject_id': sub_ds.id,
        'semester': '4th Semester'
    })
    assert res_sub2.status_code == 200
    data_sub2 = res_sub2.get_json()
    assert data_sub2['success'] is True
    assert data_sub2['attendance_type'] == 'SUBJECT'

    # 4. Check GET /api/dashboard/stats
    res_stats = client.get('/api/dashboard/stats')
    assert res_stats.status_code == 200
    data_stats = res_stats.get_json()
    # present_today MUST BE 1, NOT 3!
    assert data_stats['present_today'] == 1


def test_api_teacher_subjects_exposes_coordinator(client, app, setup_coordinator_environment):
    """Test that GET /api/teacher/subjects returns is_coordinator and coordinator_assignments."""
    client.post('/auth/login', data={'username': 'amit', 'password': 'pass123'}, follow_redirects=True)
    res = client.get('/api/teacher/subjects')
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['is_coordinator'] is True
    assert len(data['coordinator_assignments']) >= 1
    coord = data['coordinator_assignments'][0]
    assert coord['semester'] == '4th Semester'
    assert coord['section'] == 'A'
    assert 'class_label' in coord
