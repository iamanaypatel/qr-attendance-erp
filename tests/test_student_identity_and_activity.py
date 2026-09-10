import pytest
from datetime import date, datetime, time
from app.models.user import User
from app.models.student import Student
from app.models.department import Department
from app.models.attendance import Attendance

@pytest.fixture
def multi_student_db(app):
    with app.app_context():
        dept = Department.query.filter_by(code='CSE').first()
        if not dept:
            dept = Department(name='Computer Science & Engineering', code='CSE')
            from app.extensions import db
            db.session.add(dept)
            db.session.commit()

        from app.extensions import db

        # Create Student A
        user_a = User(username='student_a', email='student_a@vsmt.edu.in', role='student', is_active=True)
        user_a.set_password('Password@123')
        db.session.add(user_a)
        db.session.commit()

        student_a = Student(
            user_id=user_a.id,
            student_id='STU2026001',
            full_name='Rahul Sharma',
            email='student_a@vsmt.edu.in',
            roll_number='CS-2026-001',
            department_id=dept.id,
            course='B.Tech CSE',
            semester='4th',
            section='A',
            qr_token=Student.generate_qr_token()
        )
        db.session.add(student_a)

        # Create Student B
        user_b = User(username='student_b', email='student_b@vsmt.edu.in', role='student', is_active=True)
        user_b.set_password('Password@123')
        db.session.add(user_b)
        db.session.commit()

        student_b = Student(
            user_id=user_b.id,
            student_id='STU2026002',
            full_name='Anjali Verma',
            email='student_b@vsmt.edu.in',
            roll_number='CS-2026-002',
            department_id=dept.id,
            course='B.Tech CSE',
            semester='4th',
            section='A',
            qr_token=Student.generate_qr_token()
        )
        db.session.add(student_b)

        # Create Student C
        user_c = User(username='student_c', email='student_c@vsmt.edu.in', role='student', is_active=True)
        user_c.set_password('Password@123')
        db.session.add(user_c)
        db.session.commit()

        student_c = Student(
            user_id=user_c.id,
            student_id='STU2026003',
            full_name='Aman Singh',
            email='student_c@vsmt.edu.in',
            roll_number='CS-2026-003',
            department_id=dept.id,
            course='B.Tech CSE',
            semester='4th',
            section='A',
            qr_token=Student.generate_qr_token()
        )
        db.session.add(student_c)

        # Create Admin
        admin_u = User.query.filter_by(username='admin').first()
        if not admin_u:
            admin_u = User(username='admin', email='admin@vsmt.edu.in', role='admin', is_active=True)
            admin_u.set_password('Admin@1234')
            db.session.add(admin_u)

        db.session.commit()
        yield db

def test_student_login_automatic_identity(client, multi_student_db):
    """Test 1: Student login identifies exact student; Student A cannot view Student B's QR or ID card."""
    # Login as Student A (Rahul Sharma)
    resp = client.post('/auth/login', data={'identity': 'student_a', 'password': 'Password@123'})
    assert resp.status_code in (200, 302)

    # 1. Check Dashboard displays Student A's identity
    dash_resp = client.get('/student/dashboard')
    assert dash_resp.status_code == 200
    assert b'Rahul Sharma' in dash_resp.data
    assert b'STU2026001' in dash_resp.data
    assert b'Anjali Verma' not in dash_resp.data
    assert b'STU2026002' not in dash_resp.data

    # 2. Check QR page shows Student A's identity
    qr_resp = client.get('/student/qr-code')
    assert qr_resp.status_code == 200
    assert b'Rahul Sharma' in qr_resp.data
    assert b'STU2026001' in qr_resp.data
    assert b'Anjali Verma' not in qr_resp.data

    # 3. Check ID Card shows Student A's identity
    id_resp = client.get('/student/id-card')
    assert id_resp.status_code == 200
    assert b'Rahul Sharma' in id_resp.data
    assert b'STU2026001' in id_resp.data
    assert b'Anjali Verma' not in id_resp.data

    # 4. Check Profile shows Student A's identity
    prof_resp = client.get('/student/profile')
    assert prof_resp.status_code == 200
    assert b'Rahul Sharma' in prof_resp.data
    assert b'STU2026001' in prof_resp.data

def test_no_student_selector_in_portal(client, multi_student_db):
    """Test 2: Student portal must NOT contain student selectors or 'Select Student Card ID' dropdown."""
    client.post('/auth/login', data={'identity': 'student_a', 'password': 'Password@123'})

    for path in ('/student/dashboard', '/student/id-card', '/student/qr-code', '/student/profile'):
        resp = client.get(path)
        assert resp.status_code == 200
        html = resp.data.decode('utf-8').lower()
        assert 'select student card id' not in html
        assert 'select student card' not in html
        assert 'choose student' not in html
        assert 'student card id dropdown' not in html

def test_url_manipulation_rejected(client, multi_student_db):
    """Test 4: Student A attempting /student/id-card/STUDENT_B_ID or query params gets 403 Forbidden."""
    client.post('/auth/login', data={'identity': 'student_a', 'password': 'Password@123'})

    # Attempt accessing Student B's ID card via URL path
    id_b_resp = client.get('/student/id-card/STU2026002')
    assert id_b_resp.status_code == 403

    # Attempt accessing Student B's QR code via URL path
    qr_b_resp = client.get('/student/qr-code/STU2026002')
    assert qr_b_resp.status_code == 403

    # Attempt accessing Student B's profile via URL path
    prof_b_resp = client.get('/student/profile/STU2026002')
    assert prof_b_resp.status_code == 403

    # Attempt query param manipulation
    query_param_resp = client.get('/student/id-card?student_id=STU2026002')
    assert query_param_resp.status_code == 403

    # Accessing own identifier path works safely (redirects to own card/qr/profile)
    id_own_resp = client.get('/student/id-card/STU2026001')
    assert id_own_resp.status_code in (200, 302)

def test_attendance_activity_feed_real_names(client, multi_student_db):
    """Test 3: Today's Activity Feed contains real student names, not generic 'Student'."""
    today = date.today()

    s_a = Student.query.filter_by(student_id='STU2026001').first()
    s_b = Student.query.filter_by(student_id='STU2026002').first()
    s_c = Student.query.filter_by(student_id='STU2026003').first()

    multi_student_db.session.add_all([
        Attendance(student_id=s_a.id, date=today, time_in=time(9, 15), status='Present', method='QR'),
        Attendance(student_id=s_b.id, date=today, time_in=time(9, 17), status='Present', method='QR'),
        Attendance(student_id=s_c.id, date=today, time_in=time(9, 21), status='Present', method='QR')
    ])
    multi_student_db.session.commit()

    # Login as Admin to inspect Attendance Feed API and Dashboard
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})

    # 1. API test: /api/attendance/today
    api_resp = client.get('/api/attendance/today')
    assert api_resp.status_code == 200
    data = api_resp.get_json()
    assert data['success'] is True
    records = data['records']
    names = [r['student_name'] for r in records]
    assert 'Rahul Sharma' in names
    assert 'Anjali Verma' in names
    assert 'Aman Singh' in names
    # Verify no record has generic "Student" name
    for r in records:
        assert r['student_name'] != 'Student'
        assert r['student']['full_name'] != 'Student'
        assert 'duration' in r

    # 2. Check present_students list in today's attendance API
    present_list = data.get('present_students', [])
    present_names = [p['full_name'] for p in present_list]
    assert 'Rahul Sharma' in present_names
    assert 'Anjali Verma' in present_names
    assert 'Aman Singh' in present_names

    # 3. Check /api/dashboard/stats
    stats_resp = client.get('/api/dashboard/stats')
    assert stats_resp.status_code == 200
    stats_data = stats_resp.get_json()
    assert stats_data['present_today'] >= 3
    stat_present_names = [p['full_name'] for p in stats_data.get('present_students', [])]
    assert 'Rahul Sharma' in stat_present_names
    assert 'Anjali Verma' in stat_present_names
    assert 'Aman Singh' in stat_present_names

    # 4. Check Web Admin Dashboard contains real student names in Present Today roster
    admin_dash = client.get('/admin/dashboard')
    assert admin_dash.status_code == 200
    assert b'Rahul Sharma' in admin_dash.data
    assert b'Anjali Verma' in admin_dash.data
    assert b'Aman Singh' in admin_dash.data
    assert b'PRESENT TODAY' in admin_dash.data

def test_api_student_me_and_login_payload(client, multi_student_db):
    """Test API login embeds student data and /api/student/me returns current student."""
    login_resp = client.post('/api/auth/login', json={'identity': 'student_a', 'password': 'Password@123'})
    assert login_resp.status_code == 200
    user_obj = login_resp.get_json()['user']
    assert user_obj['role'] == 'student'
    assert 'student' in user_obj
    assert user_obj['student']['student_id'] == 'STU2026001'
    assert user_obj['student']['full_name'] == 'Rahul Sharma'
    assert 'qr_token' in user_obj['student']

    # Test /api/student/me
    me_resp = client.get('/api/student/me')
    assert me_resp.status_code == 200
    me_data = me_resp.get_json()
    assert me_data['success'] is True
    assert me_data['student']['student_id'] == 'STU2026001'
    assert me_data['student']['full_name'] == 'Rahul Sharma'
    assert 'qr_token' in me_data['student']
    assert 'stats' in me_data['student']

def test_student_login_by_student_id_and_roll_number(client, multi_student_db):
    """Test that a student can log in using their Student ID or Roll Number directly."""
    # 1. Login using Student ID 'STU2026001'
    resp_sid = client.post('/api/auth/login', json={'identity': 'STU2026001', 'password': 'Password@123'})
    assert resp_sid.status_code == 200
    data_sid = resp_sid.get_json()
    assert data_sid['user']['student']['student_id'] == 'STU2026001'
    assert data_sid['user']['student']['full_name'] == 'Rahul Sharma'

    # Logout
    client.get('/auth/logout')

    # 2. Login using Roll Number 'CS-2026-002' (Anjali Verma)
    resp_roll = client.post('/api/auth/login', json={'identity': 'CS-2026-002', 'password': 'Password@123'})
    assert resp_roll.status_code == 200
    data_roll = resp_roll.get_json()
    assert data_roll['user']['student']['student_id'] == 'STU2026002'
    assert data_roll['user']['student']['full_name'] == 'Anjali Verma'

def test_unlinked_student_account_handling(client, multi_student_db):
    """Test unlinked student account displays clear warning without showing other student data."""
    # Create unlinked student user
    unlinked_user = User(username='unlinked_student', email='unlinked@vsmt.edu.in', role='student', is_active=True)
    unlinked_user.set_password('Password@123')
    multi_student_db.session.add(unlinked_user)
    multi_student_db.session.commit()

    # 1. API Login returns student: null and student_unlinked: true
    api_login = client.post('/api/auth/login', json={'identity': 'unlinked_student', 'password': 'Password@123'})
    assert api_login.status_code == 200
    u_data = api_login.get_json()['user']
    assert u_data['role'] == 'student'
    assert u_data.get('student') is None
    assert u_data.get('student_unlinked') is True

    # 2. /api/student/me returns 404 with exact message
    me_resp = client.get('/api/student/me')
    assert me_resp.status_code == 404
    err_msg = me_resp.get_json()['message']
    assert "Student profile is not linked to this account." in err_msg
    assert "Please contact the administrator." in err_msg

    # Logout
    client.get('/auth/logout')

    # 3. Web Login and Dashboard display no_profile template with exact message
    client.post('/auth/login', data={'identity': 'unlinked_student', 'password': 'Password@123'})
    dash_resp = client.get('/student/dashboard')
    assert dash_resp.status_code == 200
    html = dash_resp.data.decode('utf-8')
    assert "Student profile is not linked to this account." in html
    assert "Please contact the administrator." in html
    # Ensure no other student's data appears
    assert "STU2026001" not in html
    assert "Rahul Sharma" not in html

def test_api_student_profile_endpoint_and_param_security(client, multi_student_db):
    """Test /api/student/profile endpoint works identically to /api/student/me and enforces authorization."""
    # Login as Student A
    client.post('/api/auth/login', json={'identity': 'student_a', 'password': 'Password@123'})

    # 1. Test /api/student/profile returns Student A
    resp = client.get('/api/student/profile')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert data['student']['student_id'] == 'STU2026001'
    assert data['student']['full_name'] == 'Rahul Sharma'

    # 2. Security Test: Attemping to pass student_id=STU2026002 query param cannot leak Student B
    resp_tamper = client.get('/api/student/profile?student_id=STU2026002')
    assert resp_tamper.status_code == 200
    data_tamper = resp_tamper.get_json()
    # Server must ignore arbitrary parameter and return the authenticated student (Student A)
    assert data_tamper['student']['student_id'] == 'STU2026001'
    assert data_tamper['student']['full_name'] == 'Rahul Sharma'

    resp_tamper_me = client.get('/api/student/me?student_id=STU2026002')
    assert resp_tamper_me.status_code == 200
    data_tamper_me = resp_tamper_me.get_json()
    assert data_tamper_me['student']['student_id'] == 'STU2026001'

def test_auto_healing_user_student_link(client, multi_student_db):
    """Test auto-healing: when student record has user_id=None, user.student auto-links by student_id or email."""
    dept = Department.query.filter_by(code='CSE').first()
    from app.extensions import db

    # Create orphan Student with user_id = None
    orphan_student = Student(
        user_id=None,
        student_id='STU2026999',
        full_name='Auto Healing Student',
        email='autoheal@vsmt.edu.in',
        roll_number='CS-2026-999',
        department_id=dept.id,
        course='B.Tech CSE',
        semester='4th',
        section='A',
        qr_token=Student.generate_qr_token()
    )
    db.session.add(orphan_student)

    # Create User with username matching student_id
    heal_user = User(username='STU2026999', email='autoheal@vsmt.edu.in', role='student', is_active=True)
    heal_user.set_password('Password@123')
    db.session.add(heal_user)
    db.session.commit()

    # Login as this user
    login_resp = client.post('/api/auth/login', json={'identity': 'STU2026999', 'password': 'Password@123'})
    assert login_resp.status_code == 200
    user_data = login_resp.get_json()['user']
    assert user_data['student'] is not None
    assert user_data['student']['student_id'] == 'STU2026999'
    assert user_data['student']['full_name'] == 'Auto Healing Student'

    # Check /api/student/profile
    prof_resp = client.get('/api/student/profile')
    assert prof_resp.status_code == 200
    assert prof_resp.get_json()['student']['student_id'] == 'STU2026999'

    # Verify student.user_id in DB was auto-healed and persisted
    refreshed_student = Student.query.filter_by(student_id='STU2026999').first()
    assert refreshed_student.user_id == heal_user.id

def test_student_a_logout_then_student_b_login_isolation(client, multi_student_db):
    """Test complete isolation when Student A logs out and Student B logs in."""
    # Student A Login
    client.post('/api/auth/login', json={'identity': 'student_a', 'password': 'Password@123'})
    resp_a = client.get('/api/student/profile')
    assert resp_a.get_json()['student']['student_id'] == 'STU2026001'

    # Logout
    client.get('/auth/logout')

    # Student B Login
    client.post('/api/auth/login', json={'identity': 'student_b', 'password': 'Password@123'})
    resp_b = client.get('/api/student/profile')
    assert resp_b.get_json()['student']['student_id'] == 'STU2026002'
    assert resp_b.get_json()['student']['full_name'] == 'Anjali Verma'

