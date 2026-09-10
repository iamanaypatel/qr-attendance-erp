import pytest
from datetime import date
from app.models.user import User
from app.models.teacher import Teacher
from app.models.student import Student
from app.models.subject import Subject
from app.models.subject_assignment import TeacherSubjectAssignment
from app.models.attendance import Attendance

def test_admin_create_edit_deactivate_assignment(client, seeded_db):
    """Admin can create, edit, toggle status, and safely delete/deactivate assignments."""
    # Log in as Admin
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})

    teacher = Teacher.query.filter_by(employee_id='TCH101').first()
    sub1 = Subject(subject_code='CS201', subject_name='DBMS', is_active=True)
    seeded_db.session.add(sub1)
    seeded_db.session.commit()

    # 1. Admin creates assignment: Teacher -> DBMS -> 4th Semester
    resp_create = client.post('/admin/subject-assignments/create', data={
        'teacher_id': teacher.id,
        'subject_id': sub1.id,
        'semester': '4th Semester',
        'course': 'B.Tech',
        'section': 'A',
        'is_active': 'y'
    }, follow_redirects=True)
    assert resp_create.status_code == 200
    assert b'successfully assigned' in resp_create.data.lower()

    assignment = TeacherSubjectAssignment.query.filter_by(
        teacher_id=teacher.id, subject_id=sub1.id, semester='4th Semester'
    ).first()
    assert assignment is not None
    assert assignment.is_active is True
    assert assignment.section == 'A'

    # 2. Duplicate assignment prevention
    resp_dup = client.post('/admin/subject-assignments/create', data={
        'teacher_id': teacher.id,
        'subject_id': sub1.id,
        'semester': '4th Semester',
        'course': 'B.Tech',
        'section': 'A',
        'is_active': 'y'
    }, follow_redirects=True)
    assert b'already exists' in resp_dup.data.lower()

    # 3. Admin edits assignment (change section to B)
    resp_edit = client.post(f'/admin/subject-assignments/{assignment.id}/edit', data={
        'teacher_id': teacher.id,
        'subject_id': sub1.id,
        'semester': '4th Semester',
        'course': 'B.Tech',
        'section': 'B',
        'is_active': 'y'
    }, follow_redirects=True)
    assert resp_edit.status_code == 200
    seeded_db.session.refresh(assignment)
    assert assignment.section == 'B'

    # 4. Toggle status
    client.post(f'/admin/subject-assignments/{assignment.id}/toggle-status')
    seeded_db.session.refresh(assignment)
    assert assignment.is_active is False

def test_single_subject_auto_select_rule_1(client, seeded_db):
    """Test A: Teacher has only 1 assigned subject. Auto-selected, no dropdown, details visible."""
    teacher = Teacher.query.filter_by(employee_id='TCH101').first()
    sub1 = Subject(subject_code='CS301', subject_name='Database Management System', is_active=True)
    seeded_db.session.add(sub1)
    seeded_db.session.commit()

    # Deactivate existing assignments for clean test state
    TeacherSubjectAssignment.query.filter_by(teacher_id=teacher.id).update({'is_active': False})
    # Assign single subject
    asgn = TeacherSubjectAssignment(
        teacher_id=teacher.id,
        subject_id=sub1.id,
        semester='4th Semester',
        course='B.Tech',
        is_active=True
    )
    seeded_db.session.add(asgn)
    seeded_db.session.commit()

    # Log in as Teacher
    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})

    # API returns 1 subject with full details
    resp_api = client.get('/api/teacher/subjects')
    assert resp_api.status_code == 200
    data = resp_api.get_json()
    assert data['count'] == 1
    sub_data = data['subjects'][0]
    assert sub_data['subject_code'] == 'CS301'
    assert sub_data['semester'] == '4th Semester'
    assert sub_data['teacher_name'] == teacher.full_name

    # Web scanner view: exactly 1 assigned subject
    resp_scanner = client.get('/attendance/scanner')
    assert resp_scanner.status_code == 200
    assert b'Database Management System' in resp_scanner.data
    assert b'CS301' in resp_scanner.data
    assert b'4th Semester' in resp_scanner.data
    # Dropdown <select id="assignmentSelect"> should NOT be rendered when count == 1
    assert b'id="assignmentSelect"' not in resp_scanner.data

def test_multiple_subjects_selection_rule_2(client, seeded_db):
    """Test B: Teacher has multiple assigned subjects. Dropdown appears, semester adapts to selection."""
    teacher = Teacher.query.filter_by(employee_id='TCH101').first()
    sub1 = Subject(subject_code='CS302', subject_name='DBMS', is_active=True)
    sub2 = Subject(subject_code='CS303', subject_name='Operating System', is_active=True)
    seeded_db.session.add_all([sub1, sub2])
    seeded_db.session.commit()

    # Clean existing
    TeacherSubjectAssignment.query.filter_by(teacher_id=teacher.id).update({'is_active': False})
    asgn1 = TeacherSubjectAssignment(teacher_id=teacher.id, subject_id=sub1.id, semester='4th Semester', is_active=True)
    asgn2 = TeacherSubjectAssignment(teacher_id=teacher.id, subject_id=sub2.id, semester='5th Semester', is_active=True)
    seeded_db.session.add_all([asgn1, asgn2])
    seeded_db.session.commit()

    # Log in as Teacher
    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})

    resp_api = client.get('/api/teacher/subjects')
    assert resp_api.status_code == 200
    data = resp_api.get_json()
    assert data['count'] == 2

    # Web scanner view: selector is visible
    resp_scanner = client.get('/attendance/scanner')
    assert resp_scanner.status_code == 200
    assert b'id="assignmentSelect"' in resp_scanner.data
    assert b'4th Semester' in resp_scanner.data
    assert b'5th Semester' in resp_scanner.data

def test_unauthorized_subject_security_rule_14(client, seeded_db):
    """Test C: Teacher A attempts to take attendance for Teacher B's subject. Backend rejects with 403."""
    teacher_a = Teacher.query.filter_by(employee_id='TCH101').first()
    # Create Teacher B
    user_b = User(username='teacher_b', email='teacher_b@vsgoi.in', role='teacher')
    user_b.set_password('Teacher@1234')
    seeded_db.session.add(user_b)
    seeded_db.session.commit()

    teacher_b = Teacher(user_id=user_b.id, employee_id='TCH102', full_name='Prof. Sharma', email=user_b.email)
    sub_b = Subject(subject_code='CS401', subject_name='Compiler Design', is_active=True)
    seeded_db.session.add_all([teacher_b, sub_b])
    seeded_db.session.commit()

    # Assign sub_b exclusively to Teacher B
    asgn_b = TeacherSubjectAssignment(teacher_id=teacher_b.id, subject_id=sub_b.id, semester='6th Semester', is_active=True)
    seeded_db.session.add(asgn_b)
    seeded_db.session.commit()

    student = Student.query.filter_by(student_id='STU2026001').first()

    # Log in as Teacher A
    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})

    # Teacher A attempts scanning for Teacher B's subject
    resp = client.post('/api/attendance/scan', json={
        'token': student.qr_token,
        'subject_id': sub_b.id,
        'semester': '6th Semester'
    })
    # Backend MUST reject with 403 Forbidden
    assert resp.status_code == 403
    data = resp.get_json()
    assert data['success'] is False
    assert 'not authorized' in data['message'].lower()

    # Ensure no attendance record was created for sub_b
    assert Attendance.query.filter_by(student_id=student.id, subject_id=sub_b.id).count() == 0

def test_zero_assigned_subjects_rule_8(client, seeded_db):
    """Test D: Teacher with zero assigned subjects sees contact admin message and scanning is blocked."""
    teacher = Teacher.query.filter_by(employee_id='TCH101').first()
    TeacherSubjectAssignment.query.filter_by(teacher_id=teacher.id).update({'is_active': False})
    seeded_db.session.commit()

    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})

    resp_api = client.get('/api/teacher/subjects')
    assert resp_api.status_code == 200
    assert resp_api.get_json()['count'] == 0

    resp_scanner = client.get('/attendance/scanner')
    assert resp_scanner.status_code == 200
    assert b'No subject has been assigned to your account' in resp_scanner.data
    assert b'disabled' in resp_scanner.data

def test_historical_attendance_retention_on_deactivation_rule_20(client, seeded_db):
    """Test E: Deactivating/removing assignment preserves historical attendance and blocks future scans."""
    teacher = Teacher.query.filter_by(employee_id='TCH101').first()
    student = Student.query.filter_by(student_id='STU2026001').first()
    sub = Subject(subject_code='CS501', subject_name='Cloud Computing', is_active=True)
    seeded_db.session.add(sub)
    seeded_db.session.commit()

    asgn = TeacherSubjectAssignment(
        teacher_id=teacher.id, subject_id=sub.id, semester='7th Semester', is_active=True
    )
    seeded_db.session.add(asgn)
    seeded_db.session.commit()

    # Log in as Teacher
    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})

    # 1. Take attendance successfully
    scan1 = client.post('/api/attendance/scan', json={
        'token': student.qr_token,
        'subject_id': sub.id,
        'semester': '7th Semester'
    })
    assert scan1.status_code == 200
    assert scan1.get_json()['success'] is True

    # Verify attendance has semester and subject recorded
    att_rec = Attendance.query.filter_by(student_id=student.id, subject_id=sub.id).first()
    assert att_rec is not None
    assert att_rec.semester == '7th Semester'
    assert att_rec.teacher_id == teacher.id

    # 2. Deactivate the assignment
    asgn.is_active = False
    seeded_db.session.commit()

    # 3. Verify historical record is PRESERVED
    retained_att = Attendance.query.filter_by(student_id=student.id, subject_id=sub.id).first()
    assert retained_att is not None
    assert retained_att.semester == '7th Semester'

    # 4. New attendance attempt is BLOCKED
    student2 = Student(
        student_id='STU2026002',
        full_name='Bob Jones',
        email='student2@test.local',
        department_id=student.department_id,
        course=student.course,
        semester=student.semester,
        roll_number='CS02',
        qr_token=Student.generate_qr_token()
    )
    seeded_db.session.add(student2)
    seeded_db.session.commit()

    scan2 = client.post('/api/attendance/scan', json={
        'token': student2.qr_token,
        'subject_id': sub.id,
        'semester': '7th Semester'
    })
    assert scan2.status_code == 403
    assert scan2.get_json()['success'] is False

def test_same_subject_different_semesters_rule_16(client, seeded_db):
    """Test: Same subject (DBMS) assigned in 4th Sem (Teacher A) and 6th Sem (Teacher B)."""
    teacher_a = Teacher.query.filter_by(employee_id='TCH101').first()

    user_b = User(username='teacher_prof_b', email='prof_b@vsgoi.in', role='teacher')
    user_b.set_password('Teacher@1234')
    seeded_db.session.add(user_b)
    seeded_db.session.commit()

    teacher_b = Teacher(user_id=user_b.id, employee_id='TCH103', full_name='Prof. Verma', email=user_b.email)
    sub = Subject(subject_code='CS601', subject_name='DBMS MultiSem', is_active=True)
    seeded_db.session.add_all([teacher_b, sub])
    seeded_db.session.commit()

    asgn_a = TeacherSubjectAssignment(teacher_id=teacher_a.id, subject_id=sub.id, semester='4th Semester', is_active=True)
    asgn_b = TeacherSubjectAssignment(teacher_id=teacher_b.id, subject_id=sub.id, semester='6th Semester', is_active=True)
    seeded_db.session.add_all([asgn_a, asgn_b])
    seeded_db.session.commit()

    student = Student.query.filter_by(student_id='STU2026001').first()

    # Log in as Teacher A
    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})

    # Teacher A can take attendance for 4th Semester
    scan_a = client.post('/api/attendance/scan', json={
        'token': student.qr_token,
        'subject_id': sub.id,
        'semester': '4th Semester'
    })
    assert scan_a.status_code == 200

    # Teacher A CANNOT take attendance for 6th Semester (assigned to Teacher B)
    scan_a_wrong = client.post('/api/attendance/scan', json={
        'token': student.qr_token,
        'subject_id': sub.id,
        'semester': '6th Semester'
    })
    assert scan_a_wrong.status_code == 403
