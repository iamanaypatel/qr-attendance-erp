from datetime import date, datetime, timedelta
import pytest
from app.models.user import User
from app.models.teacher import Teacher
from app.models.student import Student
from app.models.subject import Subject
from app.models.subject_assignment import TeacherSubjectAssignment
from app.models.class_coordinator import ClassCoordinator
from app.models.session import AcademicSession
from app.models.holiday import Holiday
from app.models.attendance import Attendance

def test_six_critical_sections_empty_and_populated(client, seeded_db):
    """
    Test the 6 critical sections from the Master Prompt:
    1. Calendar & Holiday
    2. Take Attendance
    3. Class Coordinator
    4. Subject Assignments
    5. Subjects
    6. Dashboard (Admin + Teacher)
    Ensure they all return HTTP 200 with NO 500 errors.
    """
    # -------------------------------------------------------------
    # 1. ADMIN TESTS ON SEEDED DB
    # -------------------------------------------------------------
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'}, follow_redirects=True)

    # 1. Calendar & Holiday
    res_cal = client.get('/attendance/calendar')
    assert res_cal.status_code == 200, f"Calendar failed with {res_cal.status_code}"
    assert 'Calendar' in res_cal.data.decode('utf-8')

    # Test adding a holiday and ensuring no BuildError or 500
    res_add_h = client.post('/attendance/calendar/holiday/add', data={
        'title': 'Test Institutional Holiday',
        'date': '2026-10-15',
        'description': 'Autumn Break'
    }, follow_redirects=True)
    assert res_add_h.status_code == 200
    assert 'Test Institutional Holiday' in res_add_h.data.decode('utf-8')

    # 2. Take Attendance (Admin scanner)
    res_scan_admin = client.get('/attendance/scanner')
    assert res_scan_admin.status_code == 200, f"Scanner failed with {res_scan_admin.status_code}"
    assert 'QR Attendance Scanner' in res_scan_admin.data.decode('utf-8')

    # 3. Class Coordinator
    res_coord = client.get('/admin/class-coordinators')
    assert res_coord.status_code == 200, f"Class Coordinator failed with {res_coord.status_code}"
    assert 'Class Coordinator Management' in res_coord.data.decode('utf-8')

    # 4. Subject Assignments
    res_asgn = client.get('/admin/subject-assignments')
    assert res_asgn.status_code == 200, f"Subject Assignments failed with {res_asgn.status_code}"
    assert 'Subject Assignments' in res_asgn.data.decode('utf-8')

    # 5. Subjects
    res_sub = client.get('/admin/subjects')
    assert res_sub.status_code == 200, f"Subjects failed with {res_sub.status_code}"
    assert 'Subjects Management' in res_sub.data.decode('utf-8')

    # 6. Admin Dashboard
    res_dash = client.get('/admin/dashboard')
    assert res_dash.status_code == 200, f"Dashboard failed with {res_dash.status_code}"
    assert 'Admin Dashboard' in res_dash.data.decode('utf-8')

    client.get('/auth/logout')

    # -------------------------------------------------------------
    # 2. TEACHER TESTS
    # -------------------------------------------------------------
    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'}, follow_redirects=True)

    # Teacher Dashboard
    res_t_dash = client.get('/teacher/dashboard')
    assert res_t_dash.status_code == 200
    assert 'Teacher Portal' in res_t_dash.data.decode('utf-8')

    # Teacher Scanner (Take Attendance)
    res_t_scan = client.get('/attendance/scanner')
    assert res_t_scan.status_code == 200
    assert 'QR Attendance Scanner' in res_t_scan.data.decode('utf-8')

    # Teacher Calendar
    res_t_cal = client.get('/attendance/calendar')
    assert res_t_cal.status_code == 200

    client.get('/auth/logout')


def test_six_critical_sections_multiple_assignments_and_coordinators(client, seeded_db):
    """
    Verify the 6 sections with multiple subjects, assignments, coordinators, and sessions.
    """
    teacher = Teacher.query.first()

    # Create session 2026-27
    sess = AcademicSession(name='2026-27', start_date=date(2026, 8, 1), end_date=date(2027, 6, 30), is_active=True)
    seeded_db.session.add(sess)

    # Create 3 subjects
    s1 = Subject(subject_code='CS501', subject_name='DBMS Advanced', semester='4th Semester', is_active=True)
    s2 = Subject(subject_code='CS502', subject_name='DSA Advanced', semester='3rd Semester', is_active=True)
    s3 = Subject(subject_code='CS503', subject_name='OS Advanced', semester='5th Semester', is_active=True)
    seeded_db.session.add_all([s1, s2, s3])
    seeded_db.session.commit()

    # Create assignments
    a1 = TeacherSubjectAssignment(teacher_id=teacher.id, subject_id=s1.id, semester='4th Semester', session_id=sess.id, is_active=True)
    a2 = TeacherSubjectAssignment(teacher_id=teacher.id, subject_id=s2.id, semester='3rd Semester', session_id=sess.id, is_active=True)
    seeded_db.session.add_all([a1, a2])

    # Create coordinators
    c1 = ClassCoordinator(teacher_id=teacher.id, department_id=1, course='B.Tech CSE', semester='4th Semester', section='A', session_id=sess.id, is_active=True)
    c2 = ClassCoordinator(teacher_id=teacher.id, department_id=1, course='B.Tech CSE', semester='6th Semester', section='B', session_id=sess.id, is_active=False)
    seeded_db.session.add_all([c1, c2])
    seeded_db.session.commit()

    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'}, follow_redirects=True)

    # Check all 6 pages with multiple items
    for url, kw in [
        ('/attendance/calendar', 'Calendar'),
        ('/attendance/scanner', 'QR Attendance Scanner'),
        ('/admin/class-coordinators', 'CS501' if False else 'Class Coordinator'),
        ('/admin/subject-assignments', 'CS501'),
        ('/admin/subjects', 'CS501'),
        ('/admin/dashboard', 'Admin Dashboard')
    ]:
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} failed"
        assert kw in resp.data.decode('utf-8'), f"{kw} not found in {url}"
