from datetime import date, datetime, timedelta
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.subject import Subject
from app.models.attendance import Attendance
from app.models.user import User

def test_admin_subject_crud_and_validation(client, seeded_db):
    # Log in as Admin
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})

    # 1. Create Subject
    resp = client.post('/admin/subjects/create', data={
        'subject_code': 'CS101',
        'subject_name': 'Data Structures',
        'description': 'Binary trees, heaps, graphs',
        'department_id': 1,
        'course': 'B.Tech CSE',
        'semester': '4th',
        'is_active': 'y'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Data Structures' in resp.data

    sub = Subject.query.filter_by(subject_code='CS101').first()
    assert sub is not None
    assert sub.subject_name == 'Data Structures'
    assert sub.is_active is True

    # 2. Duplicate Code Validation
    resp_dup = client.post('/admin/subjects/create', data={
        'subject_code': 'CS101',
        'subject_name': 'Duplicate Structures',
        'department_id': 1,
        'semester': '4th',
        'is_active': 'y'
    }, follow_redirects=True)
    assert resp_dup.status_code == 200
    assert b'already exists' in resp_dup.data

    # 3. Edit Subject
    resp_edit = client.post(f'/admin/subjects/{sub.id}/edit', data={
        'subject_code': 'CS101',
        'subject_name': 'Advanced Data Structures & Algorithms',
        'description': 'Updated syllabus',
        'department_id': 1,
        'course': 'B.Tech CSE',
        'semester': '4th',
        'is_active': 'y'
    }, follow_redirects=True)
    assert resp_edit.status_code == 200

    refreshed = Subject.query.get(sub.id)
    assert refreshed.subject_name == 'Advanced Data Structures & Algorithms'

    # 4. Toggle Status
    client.post(f'/admin/subjects/{sub.id}/toggle-status', follow_redirects=True)
    refreshed2 = Subject.query.get(sub.id)
    assert refreshed2.is_active is False

    client.post(f'/admin/subjects/{sub.id}/toggle-status', follow_redirects=True)
    refreshed3 = Subject.query.get(sub.id)
    assert refreshed3.is_active is True

def test_admin_assign_teachers_to_subject(client, seeded_db):
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})
    teacher = Teacher.query.filter_by(employee_id='TCH101').first()

    sub = Subject(
        subject_code='CS102',
        subject_name='Database Management System',
        department_id=1,
        semester='4th',
        is_active=True
    )
    seeded_db.session.add(sub)
    seeded_db.session.commit()

    assert not teacher.is_assigned_to_subject(sub.id)

    # Assign teacher
    resp = client.post(f'/admin/subjects/{sub.id}/assign-teachers', data={
        'teacher_ids': [teacher.id]
    }, follow_redirects=True)
    assert resp.status_code == 200

    refreshed_teacher = Teacher.query.get(teacher.id)
    assert refreshed_teacher.is_assigned_to_subject(sub.id)
    assert sub in refreshed_teacher.assigned_subjects.all()

def test_admin_safe_deletion(client, seeded_db):
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})

    # Subject with no attendance -> Hard delete
    sub_empty = Subject(subject_code='CS999', subject_name='Obsolete Subject', is_active=True)
    seeded_db.session.add(sub_empty)
    seeded_db.session.commit()
    empty_id = sub_empty.id

    client.post(f'/admin/subjects/{empty_id}/delete', follow_redirects=True)
    assert Subject.query.get(empty_id) is None

    # Subject WITH attendance -> Safe soft delete (deactivate)
    sub_with_att = Subject(subject_code='CS103', subject_name='Web Technology', is_active=True)
    student = Student.query.filter_by(student_id='STU2026001').first()
    seeded_db.session.add(sub_with_att)
    seeded_db.session.commit()

    att = Attendance(
        student_id=student.id,
        subject_id=sub_with_att.id,
        date=date.today(),
        status='Present',
        method='QR'
    )
    seeded_db.session.add(att)
    seeded_db.session.commit()

    with_att_id = sub_with_att.id
    resp = client.post(f'/admin/subjects/{with_att_id}/delete', follow_redirects=True)
    assert resp.status_code == 200
    assert b'safely deactivated' in resp.data

    retained = Subject.query.get(with_att_id)
    assert retained is not None
    assert retained.is_active is False
    # Historical attendance still exists and references retained subject!
    assert retained.attendances.count() == 1

def test_teacher_subject_authorization_security(client, seeded_db):
    teacher = Teacher.query.filter_by(employee_id='TCH101').first()
    student = Student.query.filter_by(student_id='STU2026001').first()

    # Subject A: Assigned to Teacher
    sub_a = Subject(subject_code='CS101', subject_name='Data Structures', is_active=True)
    sub_a.teachers.append(teacher)
    # Subject B: NOT Assigned to Teacher
    sub_b = Subject(subject_code='CS104', subject_name='Software Engineering', is_active=True)
    seeded_db.session.add_all([sub_a, sub_b])
    seeded_db.session.commit()

    # Log in as Teacher
    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})

    # 1. Teacher can view assigned subject attendance
    resp_a = client.get(f'/teacher/subjects/{sub_a.id}/attendance')
    assert resp_a.status_code == 200
    assert b'Data Structures' in resp_a.data

    # 2. Teacher CANNOT view unassigned subject attendance
    resp_b = client.get(f'/teacher/subjects/{sub_b.id}/attendance', follow_redirects=True)
    assert b'not authorized' in resp_b.data.lower()

    # 3. Teacher can scan attendance for assigned subject
    scan_a = client.post('/api/attendance/scan', json={
        'token': student.qr_token,
        'subject_id': sub_a.id
    })
    assert scan_a.status_code == 200
    assert scan_a.get_json()['success'] is True

    # 4. Teacher CANNOT scan attendance for unassigned subject (backend security block!)
    scan_b = client.post('/api/attendance/scan', json={
        'token': student.qr_token,
        'subject_id': sub_b.id
    })
    assert scan_b.status_code == 400
    data_b = scan_b.get_json()
    assert data_b['success'] is False
    assert 'not authorized' in data_b['message'].lower()

def test_multi_subject_attendance_same_day(client, seeded_db):
    teacher = Teacher.query.filter_by(employee_id='TCH101').first()
    student = Student.query.filter_by(student_id='STU2026001').first()

    sub1 = Subject(subject_code='CS101', subject_name='Data Structures', is_active=True)
    sub2 = Subject(subject_code='CS102', subject_name='DBMS', is_active=True)
    sub1.teachers.append(teacher)
    sub2.teachers.append(teacher)
    seeded_db.session.add_all([sub1, sub2])
    seeded_db.session.commit()

    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})

    today = date.today()

    # Scan for Subject 1 (Time In)
    r1 = client.post('/api/attendance/scan', json={'token': student.qr_token, 'subject_id': sub1.id})
    assert r1.status_code == 200
    assert r1.get_json()['action'] == 'TIME_IN'

    # Scan for Subject 2 (Time In) on the SAME day!
    r2 = client.post('/api/attendance/scan', json={'token': student.qr_token, 'subject_id': sub2.id})
    assert r2.status_code == 200
    assert r2.get_json()['action'] == 'TIME_IN'

    # Verify both records exist simultaneously for this student on today's date
    att1 = Attendance.query.filter_by(student_id=student.id, date=today, subject_id=sub1.id).first()
    att2 = Attendance.query.filter_by(student_id=student.id, date=today, subject_id=sub2.id).first()
    assert att1 is not None
    assert att2 is not None
    assert att1.id != att2.id
    assert att1.teacher_id == teacher.id
    assert att2.teacher_id == teacher.id

    # Duplicate scan in same subject session is prevented:
    r_dup = client.post('/api/attendance/scan', json={'token': student.qr_token, 'subject_id': sub1.id})
    assert r_dup.get_json()['success'] is False
    assert r_dup.get_json()['action'] in ('COOLDOWN', 'ALREADY_COMPLETED')

def test_student_subject_wise_attendance_calculation(client, seeded_db):
    student = Student.query.filter_by(student_id='STU2026001').first()
    sub = Subject(subject_code='CS101', subject_name='Data Structures', department_id=1, semester='4th', is_active=True)
    seeded_db.session.add(sub)
    seeded_db.session.commit()

    # Seed 3 classes: 2 Present, 1 Absent (66.7%)
    d1 = date(2026, 9, 1)
    d2 = date(2026, 9, 2)
    d3 = date(2026, 9, 3)

    a1 = Attendance(student_id=student.id, subject_id=sub.id, date=d1, status='Present', method='QR')
    a2 = Attendance(student_id=student.id, subject_id=sub.id, date=d2, status='Present', method='QR')
    a3 = Attendance(student_id=student.id, subject_id=sub.id, date=d3, status='Absent', method='Manual')
    seeded_db.session.add_all([a1, a2, a3])
    seeded_db.session.commit()

    # Test helper method
    subject_stats = student.get_subject_wise_attendance()
    assert len(subject_stats) >= 1
    sub_stat = next(s for s in subject_stats if s['subject_id'] == sub.id)
    assert sub_stat['total_classes'] == 3
    assert sub_stat['present_classes'] == 2
    assert sub_stat['absent_classes'] == 1
    assert sub_stat['attendance_percentage'] == 66.7

    # Log in as Student
    client.post('/auth/login', data={'identity': 'student', 'password': 'Student@1234'})

    # View student web subjects page
    web_resp = client.get('/student/subjects')
    assert web_resp.status_code == 200
    assert b'Data Structures' in web_resp.data
    assert b'66.7%' in web_resp.data

    # View detailed subject history
    detail_resp = client.get(f'/student/subjects/{sub.id}')
    assert detail_resp.status_code == 200
    assert b'Data Structures' in detail_resp.data

    # API student attendance endpoint
    api_resp = client.get('/api/student/attendance')
    assert api_resp.status_code == 200
    api_data = api_resp.get_json()
    assert api_data['success'] is True
    api_sub = next(s for s in api_data['subject_wise'] if s['subject_id'] == sub.id)
    assert api_sub['attendance_percentage'] == 66.7

def test_api_subjects_endpoints(client, seeded_db):
    sub = Subject(subject_code='CS105', subject_name='Operating System', department_id=1, semester='4th', is_active=True)
    teacher = Teacher.query.filter_by(employee_id='TCH101').first()
    sub.teachers.append(teacher)
    seeded_db.session.add(sub)
    seeded_db.session.commit()

    # Login as Teacher
    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})

    # GET /api/subjects
    resp_all = client.get('/api/subjects')
    assert resp_all.status_code == 200
    data_all = resp_all.get_json()
    assert data_all['success'] is True
    assert any(s['subject_code'] == 'CS105' for s in data_all['subjects'])

    # GET /api/teacher/subjects
    resp_t = client.get('/api/teacher/subjects')
    assert resp_t.status_code == 200
    data_t = resp_t.get_json()
    assert data_t['success'] is True
    assert any(s['subject_code'] == 'CS105' for s in data_t['subjects'])
