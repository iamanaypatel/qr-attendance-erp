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
def setup_combined_env(app):
    """
    Setup clean database state for Combined Attendance testing:
    - 1 Department: Computer Science (CSE)
    - 2 Teachers: Dr. Amit Kumar (emp001, Coordinator + Faculty), Dr. Neha Sharma (emp002)
    - 4 Subjects: DBMS, DAA, OS, WebTech
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
        User.query.filter(User.username.in_(['amit_c', 'neha_c', 'rahul_c', 'priya_c'])).delete()
        db.session.commit()

        dept = Department(name="Computer Science & Engineering", code="CSE")
        db.session.add(dept)
        db.session.commit()

        # Teacher 1: Dr. Amit Kumar
        u_amit = User(username='amit_c', email='amit_c@test.edu', role='teacher', is_active=True)
        u_amit.set_password('pass123')
        db.session.add(u_amit)
        db.session.commit()

        t_amit = Teacher(user_id=u_amit.id, employee_id="EMP_C1", full_name="Dr. Amit Kumar", email=u_amit.email, department_id=dept.id, is_active=True)
        db.session.add(t_amit)

        # Teacher 2: Dr. Neha Sharma
        u_neha = User(username='neha_c', email='neha_c@test.edu', role='teacher', is_active=True)
        u_neha.set_password('pass123')
        db.session.add(u_neha)
        db.session.commit()

        t_neha = Teacher(user_id=u_neha.id, employee_id="EMP_C2", full_name="Dr. Neha Sharma", email=u_neha.email, department_id=dept.id, is_active=True)
        db.session.add(t_neha)
        db.session.commit()

        # Student 1: Rahul Sharma (CSE 4th Sem, Section A)
        u_rahul = User(username='rahul_c', email='rahul_c@test.edu', role='student', is_active=True)
        u_rahul.set_password('pass123')
        db.session.add(u_rahul)
        db.session.commit()

        s_rahul = Student(
            user_id=u_rahul.id,
            student_id="STU2026001",
            full_name="Rahul Sharma",
            email=u_rahul.email,
            department_id=dept.id,
            course="B.Tech CSE",
            semester="4th Semester",
            section="A",
            roll_number="CS01",
            qr_token="TOKEN_RAHUL_COMBINED_01",
            is_active=True
        )
        db.session.add(s_rahul)

        # Student 2: Priya Patel (CSE 4th Sem, Section B)
        u_priya = User(username='priya_c', email='priya_c@test.edu', role='student', is_active=True)
        u_priya.set_password('pass123')
        db.session.add(u_priya)
        db.session.commit()

        s_priya = Student(
            user_id=u_priya.id,
            student_id="STU2026002",
            full_name="Priya Patel",
            email=u_priya.email,
            department_id=dept.id,
            course="B.Tech CSE",
            semester="4th Semester",
            section="B",
            roll_number="CS02",
            qr_token="TOKEN_PRIYA_COMBINED_02",
            is_active=True
        )
        db.session.add(s_priya)

        # Subjects
        sub_dbms = Subject(subject_name="Database Management Systems", subject_code="CS401", department_id=dept.id, semester="4th Semester", is_active=True)
        sub_daa = Subject(subject_name="Design and Analysis of Algorithms", subject_code="CS402", department_id=dept.id, semester="4th Semester", is_active=True)
        sub_os = Subject(subject_name="Operating Systems", subject_code="CS403", department_id=dept.id, semester="4th Semester", is_active=True)
        sub_web = Subject(subject_name="Web Technology", subject_code="CS404", department_id=dept.id, semester="4th Semester", is_active=True)
        db.session.add_all([sub_dbms, sub_daa, sub_os, sub_web])
        db.session.commit()

        # Subject Assignments for Dr. Amit: DBMS, DAA, OS, WebTech
        for sub in [sub_dbms, sub_daa, sub_os, sub_web]:
            db.session.add(TeacherSubjectAssignment(
                teacher_id=t_amit.id,
                subject_id=sub.id,
                semester="4th Semester",
                section="A",
                is_active=True
            ))

        # Class Coordinator Assignment: Dr. Amit is Coordinator for CSE 4th Section A
        coord = ClassCoordinator.assign_coordinator(
            teacher_id=t_amit.id,
            department_id=dept.id,
            course="B.Tech CSE",
            semester="4th Semester",
            section="A",
            is_active=True
        )
        db.session.commit()

        env = {
            't_amit_id': t_amit.id,
            'u_amit_id': u_amit.id,
            't_neha_id': t_neha.id,
            'u_neha_id': u_neha.id,
            's_rahul_id': s_rahul.id,
            's_rahul_token': s_rahul.qr_token,
            's_priya_id': s_priya.id,
            's_priya_token': s_priya.qr_token,
            'sub_dbms_id': sub_dbms.id,
            'sub_daa_id': sub_daa.id,
            'sub_os_id': sub_os.id,
            'sub_web_id': sub_web.id,
            'dept_id': dept.id,
            'coord_id': coord.id
        }
        yield env


def test_combined_attendance_creates_two_separate_records(app, setup_combined_env):
    """
    Requirement #4, #5, #34:
    A single scan in Combined mode creates:
    - 1 General record (subject_id=None, attendance_type='GENERAL')
    - 1 Subject record (subject_id=DBMS, attendance_type='SUBJECT')
    """
    with app.app_context():
        env = setup_combined_env
        s_rahul = db.session.get(Student, env['s_rahul_id'])
        u_amit = db.session.get(User, env['u_amit_id'])
        sub_dbms = db.session.get(Subject, env['sub_dbms_id'])

        result = process_qr_attendance(
            token=env['s_rahul_token'],
            marker_user=u_amit,
            attendance_type='COMBINED',
            subject_id=sub_dbms.id
        )

        assert result['success'] is True, f"Failed: {result.get('message')}"
        assert result['attendance_type'] == 'COMBINED'
        assert result['general']['status'] == 'Present'
        assert result['subject']['status'] == 'Present'
        assert result['subject']['name'] == sub_dbms.subject_name

        # Verify DB records
        gen_records = Attendance.query.filter_by(
            student_id=s_rahul.id,
            attendance_type='GENERAL',
            subject_id=None
        ).all()
        assert len(gen_records) == 1

        sub_records = Attendance.query.filter_by(
            student_id=s_rahul.id,
            attendance_type='SUBJECT',
            subject_id=sub_dbms.id
        ).all()
        assert len(sub_records) == 1


def test_combined_rescan_no_duplicates(app, setup_combined_env):
    """
    Requirement #7, #10, #34:
    Scanning the same student in Combined mode again does NOT duplicate records.
    """
    with app.app_context():
        env = setup_combined_env
        s_rahul = db.session.get(Student, env['s_rahul_id'])
        u_amit = db.session.get(User, env['u_amit_id'])
        sub_dbms = db.session.get(Subject, env['sub_dbms_id'])

        # First scan
        res1 = process_qr_attendance(
            token=env['s_rahul_token'],
            marker_user=u_amit,
            attendance_type='COMBINED',
            subject_id=sub_dbms.id
        )
        assert res1['success'] is True

        # Second scan (rescan)
        res2 = process_qr_attendance(
            token=env['s_rahul_token'],
            marker_user=u_amit,
            attendance_type='COMBINED',
            subject_id=sub_dbms.id
        )
        assert res2['success'] is True
        # Both should be handled cleanly without duplication
        assert res2['general']['status'] in ['Present', 'Already Completed']
        assert res2['subject']['status'] in ['Present', 'Already Completed']

        # Total DB records must remain exactly 1 general and 1 subject
        gen_count = Attendance.query.filter_by(student_id=s_rahul.id, attendance_type='GENERAL').count()
        sub_count = Attendance.query.filter_by(student_id=s_rahul.id, attendance_type='SUBJECT', subject_id=sub_dbms.id).count()
        assert gen_count == 1
        assert sub_count == 1


def test_multi_subject_combined_attendance_and_zero_double_counting(app, setup_combined_env):
    """
    Requirement #20, #35:
    Same day multi-subject test:
    Combined + DBMS -> Rahul
    Combined + DAA  -> Rahul
    Combined + OS   -> Rahul
    Combined + Web  -> Rahul

    Expected:
    - GENERAL: Rahul = 1
    - SUBJECT DBMS = 1
    - SUBJECT DAA = 1
    - SUBJECT OS = 1
    - SUBJECT Web = 1
    - Present Today count in Dashboard stats must count Rahul ONCE (1, NOT 2, NOT 5!)
    """
    with app.app_context():
        env = setup_combined_env
        s_rahul = db.session.get(Student, env['s_rahul_id'])
        u_amit = db.session.get(User, env['u_amit_id'])
        sub_dbms = db.session.get(Subject, env['sub_dbms_id'])
        sub_daa = db.session.get(Subject, env['sub_daa_id'])
        sub_os = db.session.get(Subject, env['sub_os_id'])
        sub_web = db.session.get(Subject, env['sub_web_id'])

        # 1. Combined with DBMS
        r1 = process_qr_attendance(token=env['s_rahul_token'], marker_user=u_amit, attendance_type='COMBINED', subject_id=sub_dbms.id)
        assert r1['success'] is True
        assert r1['general']['status'] == 'Present'
        assert r1['subject']['status'] == 'Present'

        # 2. Combined with DAA
        r2 = process_qr_attendance(token=env['s_rahul_token'], marker_user=u_amit, attendance_type='COMBINED', subject_id=sub_daa.id)
        assert r2['success'] is True
        # General should already be completed, DAA should be marked Present
        assert r2['general']['status'] == 'Already Completed'
        assert r2['subject']['status'] == 'Present'
        assert r2['subject']['name'] == sub_daa.subject_name

        # 3. Combined with OS
        r3 = process_qr_attendance(token=env['s_rahul_token'], marker_user=u_amit, attendance_type='COMBINED', subject_id=sub_os.id)
        assert r3['success'] is True
        assert r3['general']['status'] == 'Already Completed'
        assert r3['subject']['status'] == 'Present'
        assert r3['subject']['name'] == sub_os.subject_name

        # 4. Combined with Web
        r4 = process_qr_attendance(token=env['s_rahul_token'], marker_user=u_amit, attendance_type='COMBINED', subject_id=sub_web.id)
        assert r4['success'] is True
        assert r4['general']['status'] == 'Already Completed'
        assert r4['subject']['status'] == 'Present'
        assert r4['subject']['name'] == sub_web.subject_name

        # Verify DB counts
        gen_count = Attendance.query.filter_by(student_id=s_rahul.id, attendance_type='GENERAL').count()
        assert gen_count == 1, f"Expected 1 General record, found {gen_count}"

        for sub in [sub_dbms, sub_daa, sub_os, sub_web]:
            cnt = Attendance.query.filter_by(student_id=s_rahul.id, attendance_type='SUBJECT', subject_id=sub.id).count()
            assert cnt == 1, f"Expected 1 record for subject {sub.subject_name}, found {cnt}"

        # Dashboard / Present Today Query check:
        # General attendance must count unique students = 1
        today = date.today()
        from sqlalchemy import func
        unique_present_students = db.session.query(
            func.count(func.distinct(Attendance.student_id))
        ).filter(
            Attendance.date == today,
            Attendance.attendance_type == 'GENERAL',
            Attendance.status.in_(['Present', 'Late'])
        ).scalar()

        assert unique_present_students == 1, f"Expected Present Today = 1, got {unique_present_students}"


def test_cross_type_independence(app, setup_combined_env):
    """
    Requirement #8:
    Case A: General already Present, Subject not present -> Combined marks Subject, reports General as already completed.
    Case B: Subject already Present, General not present -> Combined marks General, reports Subject as already completed.
    """
    with app.app_context():
        env = setup_combined_env
        s_rahul = db.session.get(Student, env['s_rahul_id'])
        u_amit = db.session.get(User, env['u_amit_id'])
        sub_dbms = db.session.get(Subject, env['sub_dbms_id'])
        sub_daa = db.session.get(Subject, env['sub_daa_id'])

        # CASE A: Take General attendance independently first
        r_gen = process_qr_attendance(
            token=env['s_rahul_token'],
            marker_user=u_amit,
            attendance_type='GENERAL'
        )
        assert r_gen['success'] is True
        assert r_gen['attendance']['attendance_type'] == 'GENERAL'

        # Now do Combined for DBMS
        r_comb = process_qr_attendance(
            token=env['s_rahul_token'],
            marker_user=u_amit,
            attendance_type='COMBINED',
            subject_id=sub_dbms.id
        )
        assert r_comb['success'] is True
        assert r_comb['general']['status'] == 'Already Completed'
        assert r_comb['subject']['status'] == 'Present'

        # CASE B: Clean slate for Rahul, take Subject attendance only first
        Attendance.query.filter_by(student_id=s_rahul.id).delete()
        db.session.commit()

        r_sub = process_qr_attendance(
            token=env['s_rahul_token'],
            marker_user=u_amit,
            attendance_type='SUBJECT',
            subject_id=sub_daa.id
        )
        assert r_sub['success'] is True
        assert r_sub['attendance']['attendance_type'] == 'SUBJECT'

        # Now do Combined for DAA
        r_comb2 = process_qr_attendance(
            token=env['s_rahul_token'],
            marker_user=u_amit,
            attendance_type='COMBINED',
            subject_id=sub_daa.id
        )
        assert r_comb2['success'] is True
        assert r_comb2['general']['status'] == 'Present'
        assert r_comb2['subject']['status'] == 'Already Completed'


def test_coordinator_rbac_enforcement(app, setup_combined_env):
    """
    Requirement #15:
    - Teacher who is not a coordinator cannot take Combined attendance.
    - Coordinator cannot take Combined attendance for a student of another section/class.
    - Coordinator cannot take Combined attendance for a subject they are not assigned to.
    """
    with app.app_context():
        env = setup_combined_env
        u_neha = db.session.get(User, env['u_neha_id'])
        u_amit = db.session.get(User, env['u_amit_id'])
        sub_dbms = db.session.get(Subject, env['sub_dbms_id'])

        # 1. Dr. Neha is not a coordinator: Combined should be rejected
        res1 = process_qr_attendance(
            token=env['s_rahul_token'],
            marker_user=u_neha,
            attendance_type='COMBINED',
            subject_id=sub_dbms.id
        )
        assert res1['success'] is False
        assert "not authorized" in res1['message'].lower() or "not assigned" in res1['message'].lower()

        # 2. Dr. Amit is coordinator for Sec A, but Priya is in Sec B:
        res2 = process_qr_attendance(
            token=env['s_priya_token'],
            marker_user=u_amit,
            attendance_type='COMBINED',
            subject_id=sub_dbms.id
        )
        assert res2['success'] is False
        assert "not authorized" in res2['message'].lower() or "class coordinator" in res2['message'].lower()

        # 3. Create a 5th subject not assigned to Dr. Amit
        dept = db.session.get(Department, env['dept_id'])
        unassigned_sub = Subject(subject_name="Cloud Computing", subject_code="CS405", department_id=dept.id, semester="4th Semester", is_active=True)
        db.session.add(unassigned_sub)
        db.session.commit()

        res3 = process_qr_attendance(
            token=env['s_rahul_token'],
            marker_user=u_amit,
            attendance_type='COMBINED',
            subject_id=unassigned_sub.id
        )
        assert res3['success'] is False
        assert "not authorized" in res3['message'].lower()


def test_combined_api_endpoint(client, app, setup_combined_env):
    """
    Requirement #16, #17:
    POST /api/attendance/scan with attendance_type='COMBINED'
    Returns structured JSON with general and subject components.
    """
    with app.app_context():
        env = setup_combined_env
        sub_dbms = db.session.get(Subject, env['sub_dbms_id'])

        # Login as Dr. Amit
        login_res = client.post('/api/auth/login', json={
            'identity': 'amit_c',
            'password': 'pass123'
        })
        assert login_res.status_code == 200
        token = login_res.json.get('token')
        headers = {'Authorization': f'Bearer {token}'} if token else {}

        scan_res = client.post('/api/attendance/scan', json={
            'token': env['s_rahul_token'],
            'attendance_type': 'COMBINED',
            'subject_id': sub_dbms.id
        }, headers=headers)

        assert scan_res.status_code == 200
        data = scan_res.json
        assert data['success'] is True
        assert data['attendance_type'] == 'COMBINED'
        assert data['student']['full_name'] == "Rahul Sharma"
        assert data['general']['status'] == "Present"
        assert data['subject']['status'] == "Present"
        assert data['subject']['name'] == sub_dbms.subject_name
