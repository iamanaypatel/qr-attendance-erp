import pytest
from datetime import date
from app.extensions import db
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.subject import Subject
from app.models.subject_assignment import TeacherSubjectAssignment
from app.models.attendance import Attendance
from app.models.user import User

@pytest.fixture
def setup_teacher_and_subjects(seeded_db):
    """Sets up a teacher assigned to two subjects, and two students in the semester."""
    teacher = Teacher.query.filter_by(employee_id='TCH101').first()
    student1 = Student.query.filter_by(student_id='STU2026001').first()

    # Add second student
    u2 = User(username='student2', email='student2@test.local', role='student', is_active=True)
    u2.set_password('Student@1234')
    db.session.add(u2)
    db.session.commit()

    student2 = Student(
        user_id=u2.id,
        student_id='STU2026002',
        full_name='Bob Johnson',
        email='student2@test.local',
        department_id=student1.department_id,
        course=student1.course,
        semester=student1.semester,
        roll_number='CS02',
        qr_token=Student.generate_qr_token(),
        is_active=True
    )
    db.session.add(student2)

    # Subject 1 (Assigned to teacher)
    sub1 = Subject(
        subject_code='CS201',
        subject_name='Operating Systems',
        department_id=student1.department_id,
        course='B.Tech CSE',
        semester='4th',
        is_active=True
    )
    db.session.add(sub1)

    # Subject 2 (Also assigned to teacher)
    sub2 = Subject(
        subject_code='CS202',
        subject_name='Computer Networks',
        department_id=student1.department_id,
        course='B.Tech CSE',
        semester='4th',
        is_active=True
    )
    db.session.add(sub2)

    # Subject 3 (Unassigned subject)
    sub3 = Subject(
        subject_code='CS301',
        subject_name='Compiler Design',
        department_id=student1.department_id,
        course='B.Tech CSE',
        semester='6th',
        is_active=True
    )
    db.session.add(sub3)
    db.session.commit()

    # Assign sub1 and sub2 to teacher
    asgn1 = TeacherSubjectAssignment(
        teacher_id=teacher.id,
        subject_id=sub1.id,
        semester='4th',
        department_id=student1.department_id,
        course='B.Tech CSE',
        is_active=True
    )
    asgn2 = TeacherSubjectAssignment(
        teacher_id=teacher.id,
        subject_id=sub2.id,
        semester='4th',
        department_id=student1.department_id,
        course='B.Tech CSE',
        is_active=True
    )
    db.session.add_all([asgn1, asgn2])
    db.session.commit()

    return {
        'teacher': teacher,
        'student1': student1,
        'student2': student2,
        'sub1': sub1,
        'sub2': sub2,
        'sub3': sub3
    }


def test_take_attendance_web_route_access(client, setup_teacher_and_subjects):
    # 1. Unauthenticated -> redirect to login
    resp = client.get('/attendance/take')
    assert resp.status_code == 302
    assert '/auth/login' in resp.headers['Location']

    # 2. Student -> redirect to student dashboard with access denied
    client.post('/auth/login', data={'identity': 'student', 'password': 'Student@1234'})
    resp_student = client.get('/attendance/take')
    assert resp_student.status_code == 302
    assert '/student/dashboard' in resp_student.headers['Location']

    # 3. Teacher -> 200 OK with list attendance UI
    client.get('/auth/logout')
    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})
    resp_teacher = client.get('/attendance/take')
    assert resp_teacher.status_code == 200
    assert b'Take Attendance' in resp_teacher.data
    assert b'studentsTable' in resp_teacher.data
    assert b'studentRosterBody' in resp_teacher.data


def test_teacher_roster_authorization_and_filtering(client, setup_teacher_and_subjects):
    env = setup_teacher_and_subjects
    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})

    # Missing subject_id for SUBJECT type -> 400
    resp_bad = client.get('/api/teacher/students?type=SUBJECT')
    assert resp_bad.status_code == 400

    # Unassigned subject (sub3) -> 403
    resp_unauth = client.get(f'/api/teacher/students?subject_id={env["sub3"].id}')
    assert resp_unauth.status_code == 403
    assert b'not assigned' in resp_unauth.data

    # Assigned subject (sub1) -> 200 with roster
    resp_roster = client.get(f'/api/teacher/students?subject_id={env["sub1"].id}&semester=4th')
    assert resp_roster.status_code == 200
    data = resp_roster.get_json()
    assert data['success'] is True
    assert data['count'] >= 2
    student_ids = [s['id'] for s in data['students']]
    assert env['student1'].id in student_ids
    assert env['student2'].id in student_ids

    # Querying a semester with no enrolled students returns 200 OK with empty roster, never 403
    resp_empty = client.get(f'/api/teacher/students?subject_id={env["sub1"].id}&semester=5th')
    assert resp_empty.status_code == 200
    empty_data = resp_empty.get_json()
    assert empty_data['success'] is True
    assert empty_data['count'] == 0
    assert empty_data['students'] == []

    # Querying 'All' semesters returns all enrolled students
    resp_all = client.get(f'/api/teacher/students?subject_id={env["sub1"].id}&semester=All')
    assert resp_all.status_code == 200
    all_data = resp_all.get_json()
    assert all_data['success'] is True
    assert all_data['count'] >= 2


def test_bulk_attendance_unmarked_becomes_absent(client, setup_teacher_and_subjects):
    env = setup_teacher_and_subjects
    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})

    # Submit attendance: student1 is Present, student2 is left unmarked
    payload = {
        'subject_id': env['sub1'].id,
        'semester': '4th',
        'attendance_date': date.today().isoformat(),
        'present_student_ids': [env['student1'].id]
    }

    sub_resp = client.post('/api/attendance/mark-bulk', json=payload)
    assert sub_resp.status_code == 200
    sub_data = sub_resp.get_json()
    assert sub_data['success'] is True
    assert sub_data['summary']['present'] == 1
    assert sub_data['summary']['absent'] >= 1

    # Verify student1 is marked Present
    att1 = Attendance.query.filter_by(
        student_id=env['student1'].id,
        subject_id=env['sub1'].id,
        date=date.today()
    ).first()
    assert att1 is not None
    assert att1.status == 'Present'
    assert att1.attendance_type == 'SUBJECT'
    assert att1.method == 'Manual'

    # Verify student2 was automatically marked Absent
    att2 = Attendance.query.filter_by(
        student_id=env['student2'].id,
        subject_id=env['sub1'].id,
        date=date.today()
    ).first()
    assert att2 is not None
    assert att2.status == 'Absent'
    assert att2.attendance_type == 'SUBJECT'
    assert att2.method == 'Manual'


def test_bulk_attendance_update_idempotency(client, setup_teacher_and_subjects):
    env = setup_teacher_and_subjects
    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})

    s1_id = env['student1'].id
    s2_id = env['student2'].id

    # 1. First submission: only s1 Present
    client.post('/api/attendance/mark-bulk', json={
        'subject_id': env['sub1'].id,
        'semester': '4th',
        'attendance_date': date.today().isoformat(),
        'present_student_ids': [s1_id]
    })

    # 2. Second submission: teacher modifies to mark only s2 Present
    resp2 = client.post('/api/attendance/mark-bulk', json={
        'subject_id': env['sub1'].id,
        'semester': '4th',
        'attendance_date': date.today().isoformat(),
        'present_student_ids': [s2_id]
    })
    assert resp2.status_code == 200

    # s1 should now be updated to Absent
    att1 = Attendance.query.filter_by(
        student_id=s1_id,
        subject_id=env['sub1'].id,
        date=date.today()
    ).first()
    assert att1.status == 'Absent'

    # s2 should now be updated to Present
    att2 = Attendance.query.filter_by(
        student_id=s2_id,
        subject_id=env['sub1'].id,
        date=date.today()
    ).first()
    assert att2.status == 'Present'

    # Exactly 1 record per student for this subject on this date
    assert Attendance.query.filter_by(student_id=s1_id, subject_id=env['sub1'].id, date=date.today()).count() == 1
    assert Attendance.query.filter_by(student_id=s2_id, subject_id=env['sub1'].id, date=date.today()).count() == 1


def test_multi_subject_independence_same_day(client, setup_teacher_and_subjects):
    env = setup_teacher_and_subjects
    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})

    sid = env['student1'].id

    # Mark Present in Subject 1 (e.g. Operating Systems)
    resp1 = client.post('/api/attendance/mark-bulk', json={
        'subject_id': env['sub1'].id,
        'semester': '4th',
        'attendance_date': date.today().isoformat(),
        'present_student_ids': [sid]
    })
    assert resp1.status_code == 200

    # Mark Absent in Subject 2 (e.g. Computer Networks)
    resp2 = client.post('/api/attendance/mark-bulk', json={
        'subject_id': env['sub2'].id,
        'semester': '4th',
        'attendance_date': date.today().isoformat(),
        'present_student_ids': [] # all unmarked -> absent
    })
    assert resp2.status_code == 200

    # Verify both records coexist independently on the same date
    att_sub1 = Attendance.query.filter_by(
        student_id=sid,
        subject_id=env['sub1'].id,
        date=date.today()
    ).first()
    assert att_sub1 is not None
    assert att_sub1.status == 'Present'

    att_sub2 = Attendance.query.filter_by(
        student_id=sid,
        subject_id=env['sub2'].id,
        date=date.today()
    ).first()
    assert att_sub2 is not None
    assert att_sub2.status == 'Absent'


def test_class_coordinator_general_attendance(client, setup_teacher_and_subjects):
    env = setup_teacher_and_subjects
    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})

    # Teacher is class coordinator for 4th semester
    # Submit General bulk attendance
    resp = client.post('/api/attendance/mark-bulk', json={
        'attendance_type': 'GENERAL',
        'semester': '4th',
        'attendance_date': date.today().isoformat(),
        'present_student_ids': [env['student1'].id]
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True

    # student1 is Present (GENERAL)
    att1 = Attendance.query.filter_by(
        student_id=env['student1'].id,
        date=date.today(),
        attendance_type='GENERAL'
    ).first()
    assert att1 is not None
    assert att1.status == 'Present'

    # student2 is Absent (GENERAL)
    att2 = Attendance.query.filter_by(
        student_id=env['student2'].id,
        date=date.today(),
        attendance_type='GENERAL'
    ).first()
    assert att2 is not None
    assert att2.status == 'Absent'
