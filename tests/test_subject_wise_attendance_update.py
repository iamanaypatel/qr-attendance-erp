from datetime import date, datetime, timedelta
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.subject import Subject
from app.models.attendance import Attendance
from app.models.user import User
from app.models.subject_assignment import TeacherSubjectAssignment
from app.utils.timezone import get_current_ist_date, get_current_ist_time

def test_subject_wise_attendance_switching_and_isolation(client, seeded_db):
    """
    Test exact prompt scenario:
    Teacher selects DBMS -> Student marked -> DBMS attendance updates.
    Teacher selects Data Structures -> Student marked -> Data Structures updates.
    Teacher selects Operating System -> Student marked -> Operating System updates.
    Verify:
    1. Neither record overwrites or replaces any other.
    2. All 3 subject records exist independently on the same day.
    3. Student subject-wise attendance summary updates correctly and independently.
    4. /api/attendance/today contains all subject records for the student.
    """
    teacher = Teacher.query.filter_by(employee_id='TCH101').first()
    student_a = Student.query.filter_by(student_id='STU2026001').first()
    student_b = Student.query.filter_by(student_id='STU2026002').first()

    # Create 3 Subjects: DBMS, Data Structures, Operating System
    dbms = Subject(subject_code='CS201', subject_name='DBMS', semester='4th', course='B.Tech CSE', is_active=True)
    dsa = Subject(subject_code='CS202', subject_name='Data Structures', semester='4th', course='B.Tech CSE', is_active=True)
    os_sub = Subject(subject_code='CS203', subject_name='Operating System', semester='4th', course='B.Tech CSE', is_active=True)

    seeded_db.session.add_all([dbms, dsa, os_sub])
    seeded_db.session.commit()

    # Assign all 3 subjects to teacher
    dbms.teachers.append(teacher)
    dsa.teachers.append(teacher)
    os_sub.teachers.append(teacher)
    seeded_db.session.commit()

    # Log in as Teacher
    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})

    today = get_current_ist_date()

    # -------------------------------------------------------------
    # STEP 1: Teacher takes attendance for DBMS
    # -------------------------------------------------------------
    res1 = client.post('/api/attendance/scan', json={
        'token': student_a.qr_token,
        'subject_id': dbms.id
    })
    assert res1.status_code == 200
    data1 = res1.get_json()
    assert data1['success'] is True
    assert data1['action'] == 'TIME_IN'
    assert data1['subject_id'] == dbms.id
    assert data1['attendance']['subject']['name'] == 'DBMS'

    # Verify DBMS record in DB
    att_dbms = Attendance.query.filter_by(student_id=student_a.id, date=today, subject_id=dbms.id).first()
    assert att_dbms is not None
    assert att_dbms.status == 'Present'
    dbms_time_in = att_dbms.time_in

    # -------------------------------------------------------------
    # STEP 2: Teacher switches to Data Structures and takes attendance
    # -------------------------------------------------------------
    res2 = client.post('/api/attendance/scan', json={
        'token': student_a.qr_token,
        'subject_id': dsa.id
    })
    assert res2.status_code == 200
    data2 = res2.get_json()
    assert data2['success'] is True
    assert data2['action'] == 'TIME_IN'
    assert data2['subject_id'] == dsa.id
    assert data2['attendance']['subject']['name'] == 'Data Structures'

    # Verify Data Structures record in DB
    att_dsa = Attendance.query.filter_by(student_id=student_a.id, date=today, subject_id=dsa.id).first()
    assert att_dsa is not None
    assert att_dsa.status == 'Present'

    # CRITICAL CHECK: DBMS record must still exist and be completely untouched
    att_dbms_check = Attendance.query.filter_by(student_id=student_a.id, date=today, subject_id=dbms.id).first()
    assert att_dbms_check is not None
    assert att_dbms_check.id != att_dsa.id
    assert att_dbms_check.status == 'Present'
    assert att_dbms_check.time_in == dbms_time_in

    # -------------------------------------------------------------
    # STEP 3: Teacher switches to Operating System and takes attendance
    # -------------------------------------------------------------
    res3 = client.post('/api/attendance/scan', json={
        'token': student_a.qr_token,
        'subject_id': os_sub.id
    })
    assert res3.status_code == 200
    data3 = res3.get_json()
    assert data3['success'] is True
    assert data3['action'] == 'TIME_IN'
    assert data3['subject_id'] == os_sub.id

    att_os = Attendance.query.filter_by(student_id=student_a.id, date=today, subject_id=os_sub.id).first()
    assert att_os is not None
    assert att_os.status == 'Present'

    # Verify all 3 records coexist for student_a on today
    student_today_records = Attendance.query.filter_by(student_id=student_a.id, date=today).all()
    assert len(student_today_records) == 3
    subject_ids = {r.subject_id for r in student_today_records}
    assert subject_ids == {dbms.id, dsa.id, os_sub.id}

    # -------------------------------------------------------------
    # STEP 4: Test Time Out isolation
    # -------------------------------------------------------------
    # Simulate time passing for Data Structures and perform Time Out
    now_ist = get_current_ist_time()
    att_dsa.time_in = (datetime.combine(today, now_ist) - timedelta(minutes=10)).time()
    seeded_db.session.commit()

    # Time Out scan for Data Structures
    res_out = client.post('/api/attendance/scan', json={
        'token': student_a.qr_token,
        'subject_id': dsa.id
    })
    assert res_out.status_code == 200
    data_out = res_out.get_json()
    assert data_out['action'] == 'TIME_OUT'

    # Refetch records
    att_dsa_refreshed = Attendance.query.get(att_dsa.id)
    assert att_dsa_refreshed.time_out is not None

    # Verify DBMS record has NOT been timed out or touched!
    att_dbms_refreshed = Attendance.query.get(att_dbms.id)
    assert att_dbms_refreshed.time_out is None

    # -------------------------------------------------------------
    # STEP 5: Verify /api/attendance/today multi-subject listing
    # -------------------------------------------------------------
    res_today = client.get('/api/attendance/today')
    assert res_today.status_code == 200
    today_data = res_today.get_json()
    assert today_data['success'] is True
    today_records = today_data.get('records', [])

    # Filter for student_a records
    student_a_scans = [r for r in today_records if r.get('student_id') == student_a.student_id]
    assert len(student_a_scans) >= 3
    today_sub_names = {r.get('subject_name') for r in student_a_scans}
    assert 'DBMS' in today_sub_names
    assert 'Data Structures' in today_sub_names
    assert 'Operating System' in today_sub_names

    # -------------------------------------------------------------
    # STEP 6: Student views subject-wise attendance
    # -------------------------------------------------------------
    # Log out teacher and log in as Student
    client.get('/auth/logout')
    client.post('/auth/login', data={'identity': 'student', 'password': 'Student@1234'})

    res_stu_att = client.get('/api/student/attendance')
    assert res_stu_att.status_code == 200
    stu_data = res_stu_att.get_json()

    # Verify both mobile-compatible keys and backend keys exist
    assert 'overall' in stu_data
    assert 'subjects' in stu_data
    assert 'overall_stats' in stu_data
    assert 'subject_wise' in stu_data

    subjects_list = stu_data['subjects']
    sub_map = {s['code']: s for s in subjects_list}

    assert 'CS201' in sub_map
    assert 'CS202' in sub_map
    assert 'CS203' in sub_map

    assert sub_map['CS201']['present'] >= 1
    assert sub_map['CS202']['present'] >= 1
    assert sub_map['CS203']['present'] >= 1

    # Individual subject detail endpoint
    res_detail = client.get(f'/api/student/attendance/{dbms.id}')
    assert res_detail.status_code == 200
    detail_data = res_detail.get_json()
    assert 'subject' in detail_data
    assert 'stats' in detail_data
    assert 'records' in detail_data
    assert 'history' in detail_data
    assert detail_data['stats']['present_classes'] >= 1

def test_multiple_students_across_multiple_subjects(client, seeded_db):
    """
    Test prompt requirement:
    DBMS: Student A, Student B
    Data Structures: Student A, Student C
    Verify:
    DBMS: A = Present, B = Present
    Data Structures: A = Present, C = Present
    No cross-subject contamination.
    """
    teacher = Teacher.query.filter_by(employee_id='TCH101').first()
    stu_a = Student.query.filter_by(student_id='STU2026001').first()
    stu_b = Student.query.filter_by(student_id='STU2026002').first()
    if not stu_b:
        user_b = User(username='student2', email='student2@example.com', role='student')
        user_b.set_password('Student@1234')
        seeded_db.session.add(user_b)
        seeded_db.session.flush()
        stu_b = Student(
            user_id=user_b.id,
            student_id='STU2026002',
            roll_number='CS002',
            full_name='Student Two',
            department_id=1,
            semester='4th',
            course='B.Tech CSE',
            qr_token='QR_TOKEN_STU_2'
        )
        seeded_db.session.add(stu_b)
        seeded_db.session.commit()
    
    # Create student C if not present
    stu_c = Student.query.filter_by(student_id='STU2026003').first()
    if not stu_c:
        user_c = User(username='student3', email='student3@example.com', role='student')
        user_c.set_password('Student@1234')
        seeded_db.session.add(user_c)
        seeded_db.session.flush()
        stu_c = Student(
            user_id=user_c.id,
            student_id='STU2026003',
            roll_number='CS003',
            full_name='Student Three',
            department_id=1,
            semester='4th',
            course='B.Tech CSE',
            qr_token='QR_TOKEN_STU_3'
        )
        seeded_db.session.add(stu_c)
        seeded_db.session.commit()

    dbms = Subject(subject_code='CS301', subject_name='DBMS Multistudent', semester='4th', course='B.Tech CSE', is_active=True)
    dsa = Subject(subject_code='CS302', subject_name='DSA Multistudent', semester='4th', course='B.Tech CSE', is_active=True)
    seeded_db.session.add_all([dbms, dsa])
    seeded_db.session.commit()

    dbms.teachers.append(teacher)
    dsa.teachers.append(teacher)
    seeded_db.session.commit()

    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})
    today = get_current_ist_date()

    # Mark DBMS: Student A and Student B
    r_dbms_a = client.post('/api/attendance/scan', json={'token': stu_a.qr_token, 'subject_id': dbms.id})
    r_dbms_b = client.post('/api/attendance/scan', json={'token': stu_b.qr_token, 'subject_id': dbms.id})
    assert r_dbms_a.status_code == 200 and r_dbms_a.get_json()['success'] is True
    assert r_dbms_b.status_code == 200 and r_dbms_b.get_json()['success'] is True

    # Mark DSA: Student A and Student C
    r_dsa_a = client.post('/api/attendance/scan', json={'token': stu_a.qr_token, 'subject_id': dsa.id})
    r_dsa_c = client.post('/api/attendance/scan', json={'token': stu_c.qr_token, 'subject_id': dsa.id})
    assert r_dsa_a.status_code == 200 and r_dsa_a.get_json()['success'] is True
    assert r_dsa_c.status_code == 200 and r_dsa_c.get_json()['success'] is True

    # Check DBMS attendance counts
    dbms_attendances = Attendance.query.filter_by(date=today, subject_id=dbms.id).all()
    dbms_students = {a.student_id for a in dbms_attendances}
    assert dbms_students == {stu_a.id, stu_b.id}
    assert stu_c.id not in dbms_students

    # Check DSA attendance counts
    dsa_attendances = Attendance.query.filter_by(date=today, subject_id=dsa.id).all()
    dsa_students = {a.student_id for a in dsa_attendances}
    assert dsa_students == {stu_a.id, stu_c.id}
    assert stu_b.id not in dsa_students

def test_teacher_unauthorized_subject_blocked(client, seeded_db):
    """
    Teacher can only mark attendance for subjects assigned to them.
    Attempting to mark attendance for unassigned subject returns 403 or 400.
    """
    teacher = Teacher.query.filter_by(employee_id='TCH101').first()
    stu = Student.query.filter_by(student_id='STU2026001').first()

    unassigned_sub = Subject(subject_code='CS401', subject_name='Cyber Security', semester='4th', is_active=True)
    seeded_db.session.add(unassigned_sub)
    seeded_db.session.commit()

    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})

    res = client.post('/api/attendance/scan', json={
        'token': stu.qr_token,
        'subject_id': unassigned_sub.id
    })
    assert res.status_code in (400, 403)
    data = res.get_json()
    assert data['success'] is False
    assert 'not authorized' in data['message'].lower()

def test_immediate_zero_gap_subject_switching(client, seeded_db):
    """
    Test requirement: NO TIME GAP BETWEEN SUBJECT ATTENDANCE
    Teacher completes attendance for DBMS -> immediately starts Data Structures -> immediately starts Operating System.
    Valid for 0-second, 5-second, 10-second gaps.
    No cooldown, no waiting period, no artificial delay allowed between different subjects.
    """
    teacher = Teacher.query.filter_by(employee_id='TCH101').first()
    student = Student.query.filter_by(student_id='STU2026001').first()

    sub_dbms = Subject(subject_code='CS501', subject_name='DBMS ZeroGap', semester='4th', is_active=True)
    sub_dsa = Subject(subject_code='CS502', subject_name='DSA ZeroGap', semester='4th', is_active=True)
    sub_os = Subject(subject_code='CS503', subject_name='OS ZeroGap', semester='4th', is_active=True)

    seeded_db.session.add_all([sub_dbms, sub_dsa, sub_os])
    seeded_db.session.commit()

    sub_dbms.teachers.append(teacher)
    sub_dsa.teachers.append(teacher)
    sub_os.teachers.append(teacher)
    seeded_db.session.commit()

    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})
    today = get_current_ist_date()

    # 1. Mark DBMS attendance for student
    r1 = client.post('/api/attendance/scan', json={
        'token': student.qr_token,
        'subject_id': sub_dbms.id
    })
    assert r1.status_code == 200
    d1 = r1.get_json()
    assert d1['success'] is True
    assert d1['action'] == 'TIME_IN'

    # 2. IMMEDIATELY (0 seconds gap) mark Data Structures attendance for the same student
    r2 = client.post('/api/attendance/scan', json={
        'token': student.qr_token,
        'subject_id': sub_dsa.id
    })
    assert r2.status_code == 200
    d2 = r2.get_json()
    assert d2['success'] is True
    assert d2['action'] == 'TIME_IN'
    assert d2['action'] != 'COOLDOWN'

    # 3. IMMEDIATELY mark OS attendance for the same student
    r3 = client.post('/api/attendance/scan', json={
        'token': student.qr_token,
        'subject_id': sub_os.id
    })
    assert r3.status_code == 200
    d3 = r3.get_json()
    assert d3['success'] is True
    assert d3['action'] == 'TIME_IN'

    # Verify all 3 records created independently
    att_dbms = Attendance.query.filter_by(student_id=student.id, date=today, subject_id=sub_dbms.id).first()
    att_dsa = Attendance.query.filter_by(student_id=student.id, date=today, subject_id=sub_dsa.id).first()
    att_os = Attendance.query.filter_by(student_id=student.id, date=today, subject_id=sub_os.id).first()

    assert att_dbms is not None and att_dbms.status == 'Present'
    assert att_dsa is not None and att_dsa.status == 'Present'
    assert att_os is not None and att_os.status == 'Present'
    assert len({att_dbms.id, att_dsa.id, att_os.id}) == 3

