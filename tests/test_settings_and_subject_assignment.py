from datetime import date
import pytest
from app.models.session import AcademicSession
from app.models.subject import Subject
from app.models.teacher import Teacher
from app.models.department import Department
from app.models.subject_assignment import TeacherSubjectAssignment
from app.models.attendance import Attendance
from app.models.student import Student
from app.models.user import User

def test_academic_session_create_and_validation(client, seeded_db):
    """Admin can create a new Academic Session with validation."""
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})

    # 1. Create a valid session
    resp = client.post('/admin/sessions/create', data={
        'name': '2026-27',
        'start_date': '2026-08-01',
        'end_date': '2027-06-30',
        'is_active': '1'
    }, follow_redirects=True)
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert '2026-27' in html
    assert 'Active Session' in html

    created = AcademicSession.query.filter_by(name='2026-27').first()
    assert created is not None
    assert created.start_date == date(2026, 8, 1)
    assert created.end_date == date(2027, 6, 30)
    assert created.is_active is True

    # 2. Prevent duplicate session name
    resp_dup = client.post('/admin/sessions/create', data={
        'name': '2026-27',
        'start_date': '2026-08-01',
        'end_date': '2027-06-30'
    }, follow_redirects=True)
    assert resp_dup.status_code == 200
    assert 'already exists' in resp_dup.data.decode('utf-8').lower()

    # 3. Invalid date order (start_date > end_date)
    resp_inv = client.post('/admin/sessions/create', data={
        'name': '2030-31',
        'start_date': '2031-01-01',
        'end_date': '2030-01-01'
    }, follow_redirects=True)
    assert resp_inv.status_code == 200
    assert 'cannot be after' in resp_inv.data.decode('utf-8').lower()
    assert AcademicSession.query.filter_by(name='2030-31').first() is None


def test_academic_session_single_active_rule_and_history_preserved(client, seeded_db):
    """Enforce single active academic session rule without affecting historical attendance."""
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})

    # Existing active session (e.g. 2025-2026)
    s1 = AcademicSession.query.filter_by(name='2025-2026').first()
    if not s1:
        s1 = AcademicSession(name='2025-2026', start_date=date(2025, 8, 1), end_date=date(2026, 6, 30), is_active=True)
        seeded_db.session.add(s1)
        seeded_db.session.commit()
    assert s1.is_active is True

    # Create a historical attendance record linked to teacher and subject
    teacher = Teacher.query.first()
    student = Student.query.first()
    sub = Subject.query.first()
    if not sub:
        sub = Subject(subject_code='CS101-HIST', subject_name='Historical Subject', semester='4th Semester', is_active=True)
        seeded_db.session.add(sub)
        seeded_db.session.commit()

    hist_att = Attendance(
        student_id=student.id,
        teacher_id=teacher.id,
        subject_id=sub.id,
        semester='4th Semester',
        date=date(2025, 9, 1),
        status='Present',
        attendance_type='subject_wise'
    )
    seeded_db.session.add(hist_att)
    seeded_db.session.commit()
    hist_att_id = hist_att.id

    # Create new session 2026-27 set to Active
    client.post('/admin/sessions/create', data={
        'name': '2026-27',
        'start_date': '2026-08-01',
        'end_date': '2027-06-30',
        'is_active': '1'
    }, follow_redirects=True)

    seeded_db.session.expire_all()
    s1_reloaded = seeded_db.session.get(AcademicSession, s1.id)
    s2 = AcademicSession.query.filter_by(name='2026-27').first()
    assert s2.is_active is True
    assert s1_reloaded.is_active is False  # Deactivated automatically

    # Verify historical attendance record is unchanged
    reloaded_att = seeded_db.session.get(Attendance, hist_att_id)
    assert reloaded_att is not None
    assert reloaded_att.semester == '4th Semester'
    assert reloaded_att.subject_id == sub.id
    assert reloaded_att.status == 'Present'


def test_academic_session_edit_persists_immediately(client, seeded_db):
    """Admin can edit Academic Session (e.g. 2026-27 -> 2027-28) and changes persist immediately."""
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})

    ses = AcademicSession(name='2026-27', start_date=date(2026, 8, 1), end_date=date(2027, 6, 30), is_active=False)
    seeded_db.session.add(ses)
    seeded_db.session.commit()

    resp = client.post(f'/admin/sessions/{ses.id}/edit', data={
        'name': '2027-28',
        'start_date': '2027-08-01',
        'end_date': '2028-06-30',
        'is_active': '1'
    }, follow_redirects=True)
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert '2027-28' in html
    assert '<td class="fw-semibold text-dark">2026-27</td>' not in html

    assert AcademicSession.query.filter_by(name='2026-27').first() is None
    assert AcademicSession.query.filter_by(name='2027-28').first() is not None

    seeded_db.session.expire_all()
    reloaded = seeded_db.session.get(AcademicSession, ses.id)
    assert reloaded.name == '2027-28'
    assert reloaded.start_date == date(2027, 8, 1)
    assert reloaded.end_date == date(2028, 6, 30)
    assert reloaded.is_active is True

    # Test json endpoint for edit prefilling
    json_resp = client.get(f'/admin/sessions/{ses.id}/json')
    assert json_resp.status_code == 200
    jdata = json_resp.get_json()
    assert jdata['name'] == '2027-28'
    assert jdata['start_date'] == '2027-08-01'


def test_subjects_management_faculty_name_and_semester_display(client, seeded_db):
    """Subject Management displays real Assigned Faculty name and formatted Semester name."""
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})

    # Create teacher Dr. Amit Kumar
    user = User(username='amit_kumar', email='amit.kumar@vsmt.edu.in', role='teacher', is_active=True)
    user.set_password('Teacher@1234')
    seeded_db.session.add(user)
    seeded_db.session.commit()

    teacher = Teacher(
        user_id=user.id,
        employee_id='TCH901',
        full_name='Dr. Amit Kumar',
        email='amit.kumar@vsmt.edu.in',
        is_active=True
    )
    seeded_db.session.add(teacher)

    # Create subject DBMS CS102
    sub = Subject(
        subject_code='CS102-DBMS',
        subject_name='Database Management System',
        semester='4th',
        is_active=True
    )
    seeded_db.session.add(sub)
    seeded_db.session.commit()

    # Create assignment
    asgn = TeacherSubjectAssignment(
        teacher_id=teacher.id,
        subject_id=sub.id,
        semester='4th',
        is_active=True
    )
    seeded_db.session.add(asgn)
    seeded_db.session.commit()

    resp = client.get('/admin/subjects')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')

    assert 'Database Management System' in html
    assert 'CS102-DBMS' in html
    assert 'Dr. Amit Kumar' in html
    assert '4th Semester' in html
    assert 'None' not in html
    assert 'null' not in html


def test_subjects_management_multiple_faculty_distinct_semesters(client, seeded_db):
    """Subject assigned to multiple faculties across different semesters displays all assignments correctly."""
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})

    user_a = User(username='amit_k2', email='amit2@vsmt.edu.in', role='teacher', is_active=True)
    user_a.set_password('Teacher@1234')
    user_b = User(username='neha_s', email='neha@vsmt.edu.in', role='teacher', is_active=True)
    user_b.set_password('Teacher@1234')
    seeded_db.session.add_all([user_a, user_b])
    seeded_db.session.commit()

    t_amit = Teacher(user_id=user_a.id, employee_id='TCH902', full_name='Dr. Amit Kumar', email='amit2@vsmt.edu.in', is_active=True)
    t_neha = Teacher(user_id=user_b.id, employee_id='TCH903', full_name='Dr. Neha Sharma', email='neha@vsmt.edu.in', is_active=True)
    seeded_db.session.add_all([t_amit, t_neha])

    sub = Subject(subject_code='CS109-MULTI', subject_name='Advanced Systems', is_active=True)
    seeded_db.session.add(sub)
    seeded_db.session.commit()

    asgn1 = TeacherSubjectAssignment(teacher_id=t_amit.id, subject_id=sub.id, semester='4th Semester', is_active=True)
    asgn2 = TeacherSubjectAssignment(teacher_id=t_neha.id, subject_id=sub.id, semester='6th Semester', is_active=True)
    seeded_db.session.add_all([asgn1, asgn2])
    seeded_db.session.commit()

    resp = client.get('/admin/subjects')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')

    assert 'Advanced Systems' in html
    assert 'Dr. Amit Kumar' in html
    assert 'Dr. Neha Sharma' in html
    assert '4th Semester' in html
    assert '6th Semester' in html


def test_subjects_management_unassigned_empty_state(client, seeded_db):
    """Subject with no faculty and no semester displays 'Not Assigned' and 'Not Set'."""
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})

    unassigned_sub = Subject(
        subject_code='CS888-EMPTY',
        subject_name='Quantum Computing',
        semester=None,
        is_active=True
    )
    seeded_db.session.add(unassigned_sub)
    seeded_db.session.commit()

    resp = client.get('/admin/subjects')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')

    assert 'Quantum Computing' in html
    assert 'Not Assigned' in html
    assert 'Not Set' in html


def test_subject_assignment_edit_flow_no_stale_teacher_or_semester(client, seeded_db):
    """Editing faculty and semester in Subject Assignment updates immediately with no stale values."""
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})

    u1 = User(username='teach1', email='t1@vsmt.edu.in', role='teacher', is_active=True)
    u1.set_password('Teacher@1234')
    u2 = User(username='teach2', email='t2@vsmt.edu.in', role='teacher', is_active=True)
    u2.set_password('Teacher@1234')
    seeded_db.session.add_all([u1, u2])
    seeded_db.session.commit()

    t1 = Teacher(user_id=u1.id, employee_id='TCH701', full_name='Dr. Original Teacher', email='t1@vsmt.edu.in', is_active=True)
    t2 = Teacher(user_id=u2.id, employee_id='TCH702', full_name='Dr. Replacement Teacher', email='t2@vsmt.edu.in', is_active=True)
    seeded_db.session.add_all([t1, t2])

    sub = Subject(subject_code='CS303-EDIT', subject_name='Compiler Design', semester='4th', is_active=True)
    seeded_db.session.add(sub)
    seeded_db.session.commit()

    asgn = TeacherSubjectAssignment(
        teacher_id=t1.id,
        subject_id=sub.id,
        semester='4th Semester',
        is_active=True
    )
    sub.teachers.append(t1)
    seeded_db.session.add(asgn)
    seeded_db.session.commit()

    # 1. Edit faculty to Dr. Replacement Teacher
    resp_edit1 = client.post(f'/admin/subject-assignments/{asgn.id}/edit', data={
        'teacher_id': t2.id,
        'subject_id': sub.id,
        'semester': '4th Semester',
        'is_active': 'y'
    }, follow_redirects=True)
    assert resp_edit1.status_code == 200

    seeded_db.session.expire_all()
    reloaded_sub = seeded_db.session.get(Subject, sub.id)
    faculty_names = [f['name'] for f in reloaded_sub.assigned_faculty_list]
    assert 'Dr. Replacement Teacher' in faculty_names
    assert 'Dr. Original Teacher' not in faculty_names

    # 2. Edit semester to 5th Semester
    resp_edit2 = client.post(f'/admin/subject-assignments/{asgn.id}/edit', data={
        'teacher_id': t2.id,
        'subject_id': sub.id,
        'semester': '5th Semester',
        'is_active': 'y'
    }, follow_redirects=True)
    assert resp_edit2.status_code == 200

    seeded_db.session.expire_all()
    reloaded_sub2 = seeded_db.session.get(Subject, sub.id)
    assert '5th Semester' in reloaded_sub2.display_semesters
    assert '4th Semester' not in reloaded_sub2.display_semesters
