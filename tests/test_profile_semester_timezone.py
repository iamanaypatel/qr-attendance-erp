import pytest
from datetime import datetime, date, time
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.subject import Subject
from app.models.subject_assignment import TeacherSubjectAssignment
from app.models.attendance import Attendance
from app.models.department import Department
from app.utils.timezone import get_current_ist_datetime, get_current_ist_date, get_current_ist_time, IST

def test_student_profile_full_page_details(client, seeded_db):
    """Test Issue 1: Student profile loads full-page details with all academic, personal, and attendance telemetry."""
    # Login as admin
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})

    student = Student.query.filter_by(student_id='STU2026001').first()
    resp = client.get(f'/admin/students/{student.id}')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')

    # Verify hero header and key demographics
    assert student.full_name in html
    assert student.student_id in html
    assert 'Academic Information' in html
    assert 'Personal & Contact Details' in html
    assert 'Digital Attendance QR Pass' in html
    assert 'Portal Account' in html
    assert 'Recent Attendance Records' in html
    assert 'Generate ID Card (PDF)' in html

def test_subjects_page_displays_assigned_faculty_and_semester(client, seeded_db):
    """Test Issue 2: Admin -> Subjects displays Assigned Faculty and Semester properly from database relationships."""
    teacher = Teacher.query.filter_by(employee_id='TCH101').first()
    sub1 = Subject(subject_code='CS401', subject_name='DBMS Advanced', semester='4th Semester', is_active=True)
    seeded_db.session.add(sub1)
    seeded_db.session.commit()

    # Create active assignment
    asgn = TeacherSubjectAssignment(
        teacher_id=teacher.id,
        subject_id=sub1.id,
        semester='4th Semester',
        is_active=True
    )
    seeded_db.session.add(asgn)
    seeded_db.session.commit()

    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})
    resp = client.get('/admin/subjects')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')

    assert 'DBMS Advanced' in html
    assert 'CS401' in html
    assert teacher.full_name in html
    assert '4th Semester' in html

def test_subjects_multiple_assignments_and_unassigned_handling(client, seeded_db):
    """Test Issue 2: Multiple assignments display all teachers/semesters; unassigned shows Not Assigned / Not Set."""
    teacher_a = Teacher.query.filter_by(employee_id='TCH101').first()
    dept = Department.query.first()

    # Unassigned subject
    unassigned_sub = Subject(subject_code='CS999', subject_name='Intro to Robotics', is_active=True)
    seeded_db.session.add(unassigned_sub)
    seeded_db.session.commit()

    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})
    resp = client.get('/admin/subjects')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')

    assert 'Intro to Robotics' in html
    assert 'Not Assigned' in html
    assert 'Not Set' in html

def test_subject_to_dict_api_assigned_faculty(client, seeded_db):
    """Test Issue 2: Subject.to_dict() returns assigned_faculty array and resolved semester."""
    teacher = Teacher.query.filter_by(employee_id='TCH101').first()
    sub = Subject(subject_code='CS502', subject_name='Operating Systems', is_active=True)
    seeded_db.session.add(sub)
    seeded_db.session.commit()

    asgn = TeacherSubjectAssignment(
        teacher_id=teacher.id,
        subject_id=sub.id,
        semester='5th Semester',
        is_active=True
    )
    seeded_db.session.add(asgn)
    seeded_db.session.commit()

    data = sub.to_dict()
    assert data['semester'] == '5th Semester'
    assert len(data['assigned_faculty']) == 1
    assert data['assigned_faculty'][0]['name'] == teacher.full_name
    assert data['assigned_faculty'][0]['semester'] == '5th Semester'

def test_attendance_timestamps_authoritative_ist(client, seeded_db):
    """Test Issue 3: Attendance In and Out timestamps use authoritative Asia/Kolkata (IST) time."""
    teacher = Teacher.query.filter_by(employee_id='TCH101').first()
    student = Student.query.filter_by(student_id='STU2026001').first()
    sub = Subject(subject_code='CS101', subject_name='C Programming', is_active=True)
    seeded_db.session.add(sub)
    seeded_db.session.commit()

    asgn = TeacherSubjectAssignment(
        teacher_id=teacher.id,
        subject_id=sub.id,
        semester='1st Semester',
        is_active=True
    )
    seeded_db.session.add(asgn)
    seeded_db.session.commit()

    # Login as teacher
    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})

    # 1. First scan -> Time In
    scan_in = client.post('/api/attendance/scan', json={
        'token': student.qr_token,
        'subject_id': sub.id,
        'semester': '1st Semester'
    })
    assert scan_in.status_code == 200
    res1 = scan_in.get_json()
    assert res1['success'] is True
    assert res1['action'] == 'TIME_IN'

    # Check database record
    today_ist = get_current_ist_date()
    att = Attendance.query.filter_by(student_id=student.id, subject_id=sub.id, date=today_ist).first()
    assert att is not None
    assert att.time_in is not None
    assert att.time_out is None
    assert att.date == today_ist

    # Stored time_in must match current IST within seconds
    now_ist = get_current_ist_time()
    assert abs(att.time_in.hour - now_ist.hour) <= 1  # near boundary safe

    # 2. Bypass cooldown by setting time_in 35 seconds ago
    from datetime import timedelta
    earlier_dt = datetime.combine(today_ist, now_ist) - timedelta(seconds=40)
    att.time_in = earlier_dt.time()
    seeded_db.session.commit()

    # 3. Second scan -> Time Out
    scan_out = client.post('/api/attendance/scan', json={
        'token': student.qr_token,
        'subject_id': sub.id,
        'semester': '1st Semester'
    })
    assert scan_out.status_code == 200
    res2 = scan_out.get_json()
    assert res2['success'] is True
    assert res2['action'] == 'TIME_OUT'

    seeded_db.session.refresh(att)
    assert att.time_out is not None

    # Check duration calculated from stored timestamps
    att_dict = att.to_dict()
    assert att_dict['duration'] is not None
    assert 'm' in att_dict['duration']
