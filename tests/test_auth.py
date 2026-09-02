from app.models.user import User

def test_password_hashing():
    user = User(username='testuser', email='test@test.local', role='student')
    user.set_password('Secret@123')
    assert user.password_hash != 'Secret@123'
    assert user.check_password('Secret@123') is True
    assert user.check_password('WrongPassword') is False

def test_admin_login(client, seeded_db):
    response = client.post('/auth/login', data={
        'identity': 'admin',
        'password': 'Admin@1234'
    }, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['Location'] == '/admin/dashboard'

def test_teacher_login(client, seeded_db):
    response = client.post('/auth/login', data={
        'identity': 'teacher',
        'password': 'Teacher@1234'
    }, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['Location'] == '/teacher/dashboard'

def test_student_login(client, seeded_db):
    response = client.post('/auth/login', data={
        'identity': 'student@test.local', # test login by email
        'password': 'Student@1234'
    }, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['Location'] == '/student/dashboard'

def test_invalid_login(client, seeded_db):
    response = client.post('/auth/login', data={
        'identity': 'admin',
        'password': 'WrongPassword123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Invalid credentials' in response.data

def test_logout(client, seeded_db):
    # Log in first
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})
    # Log out
    response = client.get('/auth/logout', follow_redirects=False)
    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']

def test_unauthenticated_protected_route(client):
    response = client.get('/admin/dashboard', follow_redirects=False)
    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']

def test_role_based_access_control(client, seeded_db):
    # Log in as Student
    client.post('/auth/login', data={'identity': 'student', 'password': 'Student@1234'})
    # Try to access Admin dashboard -> should be denied and redirected to student dashboard
    response = client.get('/admin/dashboard', follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['Location'] == '/student/dashboard'
