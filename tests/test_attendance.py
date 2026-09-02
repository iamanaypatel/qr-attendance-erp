from datetime import date, datetime, timedelta
from app.models.student import Student
from app.models.attendance import Attendance
from app.attendance.services import process_qr_attendance
from app.models.user import User

def test_qr_attendance_lifecycle(client, seeded_db):
    # Log in as Teacher
    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})
    teacher_user = User.query.filter_by(username='teacher').first()
    student = Student.query.filter_by(student_id='STU2026001').first()

    # 1. First Scan -> Time In
    resp1 = client.post('/api/attendance/scan', json={'token': student.qr_token})
    assert resp1.status_code == 200
    data1 = resp1.get_json()
    assert data1['success'] is True
    assert data1['action'] == 'TIME_IN'
    assert 'Time In marked successfully' in data1['message']

    record = Attendance.query.filter_by(student_id=student.id, date=date.today()).first()
    assert record is not None
    assert record.time_in is not None
    assert record.time_out is None
    assert record.status == 'Present'
    assert record.method == 'QR'

    # Fast forward the cooldown to test Time Out
    record.time_in = (datetime.now() - timedelta(minutes=5)).time()
    seeded_db.session.commit()

    # 2. Second Scan -> Time Out
    resp2 = client.post('/api/attendance/scan', json={'token': student.qr_token})
    assert resp2.status_code == 200
    data2 = resp2.get_json()
    assert data2['success'] is True
    assert data2['action'] == 'TIME_OUT'
    assert 'Time Out marked successfully' in data2['message']

    record = Attendance.query.filter_by(student_id=student.id, date=date.today()).first()
    assert record.time_out is not None

    # 3. Third Scan -> Already Completed (Duplicate prevention)
    resp3 = client.post('/api/attendance/scan', json={'token': student.qr_token})
    assert resp3.status_code == 200
    data3 = resp3.get_json()
    assert data3['success'] is False
    assert data3['action'] == 'ALREADY_COMPLETED'
    assert 'already completed' in data3['message'].lower()

def test_invalid_qr_token(client, seeded_db):
    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})
    resp = client.post('/api/attendance/scan', json={'token': 'non-existent-fake-token-xyz'})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data['success'] is False
    assert 'Unrecognized QR code' in data['message']

def test_student_cannot_scan_api(client, seeded_db):
    # Log in as student
    client.post('/auth/login', data={'identity': 'student', 'password': 'Student@1234'})
    student = Student.query.filter_by(student_id='STU2026001').first()
    resp = client.post('/api/attendance/scan', json={'token': student.qr_token})
    assert resp.status_code == 403

def test_manual_attendance_marking(client, seeded_db):
    # Log in as Admin
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})
    student = Student.query.filter_by(student_id='STU2026001').first()

    test_date = date.today() - timedelta(days=2)

    resp = client.post('/attendance/manual', data={
        'student_id': str(student.id),
        'date': test_date.strftime('%Y-%m-%d'),
        'status': 'Present',
        'time_in': '09:15',
        'time_out': '16:45',
        'remarks': 'Test manual override'
    }, follow_redirects=True)
    assert resp.status_code == 200

    rec = Attendance.query.filter_by(student_id=student.id, date=test_date).first()
    assert rec is not None
    assert rec.status == 'Present'
    assert rec.method == 'Admin'
    assert rec.remarks == 'Test manual override'
