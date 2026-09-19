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


def test_firebase_login_endpoints(client, seeded_db, monkeypatch):
    # 1. Missing token
    res = client.post('/auth/firebase-login', json={})
    assert res.status_code == 400
    assert 'Missing Firebase ID token' in res.json['message']

    # 2. Mock token verification for existing admin
    import requests
    class MockResp:
        status_code = 200
        headers = {'content-type': 'application/json'}
        def json(self):
            return {
                'users': [{
                    'localId': 'mock_fb_uid_admin',
                    'email': 'admin@test.local',
                    'emailVerified': True,
                    'providerUserInfo': [{'providerId': 'google.com'}]
                }]
            }

    monkeypatch.setattr(requests, 'post', lambda *args, **kwargs: MockResp())

    res = client.post('/auth/firebase-login', json={
        'id_token': 'mock_valid_token_123',
        'email': 'admin@test.local'
    })
    assert res.status_code == 200
    assert res.json['success'] is True
    assert res.json['user']['role'] == 'admin'
    assert res.json['redirect_url'] == '/admin/dashboard'


def test_google_auth_student_login(client, seeded_db, monkeypatch):
    import requests
    class MockResp:
        status_code = 200
        headers = {'content-type': 'application/json'}
        def json(self):
            return {
                'users': [{
                    'localId': 'mock_fb_uid_student',
                    'email': 'STUDENT@test.local',  # Test case normalization
                    'emailVerified': True,
                    'providerUserInfo': [{'providerId': 'google.com'}]
                }]
            }

    monkeypatch.setattr(requests, 'post', lambda *args, **kwargs: MockResp())

    res = client.post('/api/auth/google', json={'id_token': 'valid_student_token'})
    assert res.status_code == 200
    assert res.json['success'] is True
    assert res.json['user']['role'] == 'student'
    assert res.json['user']['email'] == 'student@test.local'
    assert 'token' in res.json


def test_google_auth_teacher_login(client, seeded_db, monkeypatch):
    import requests
    class MockResp:
        status_code = 200
        headers = {'content-type': 'application/json'}
        def json(self):
            return {
                'users': [{
                    'localId': 'mock_fb_uid_teacher',
                    'email': 'teacher@test.local',
                    'emailVerified': True,
                    'providerUserInfo': [{'providerId': 'google.com'}]
                }]
            }

    monkeypatch.setattr(requests, 'post', lambda *args, **kwargs: MockResp())

    res = client.post('/api/auth/google', json={'id_token': 'valid_teacher_token'})
    assert res.status_code == 200
    assert res.json['success'] is True
    assert res.json['user']['role'] == 'teacher'


def test_google_auth_unregistered_email_denied(client, seeded_db, monkeypatch):
    import requests
    class MockResp:
        status_code = 200
        headers = {'content-type': 'application/json'}
        def json(self):
            return {
                'users': [{
                    'localId': 'mock_fb_uid_stranger',
                    'email': 'stranger@gmail.com',
                    'emailVerified': True,
                    'providerUserInfo': [{'providerId': 'google.com'}]
                }]
            }

    monkeypatch.setattr(requests, 'post', lambda *args, **kwargs: MockResp())

    res = client.post('/api/auth/google', json={'id_token': 'stranger_token'})
    assert res.status_code == 401
    assert res.json['success'] is False
    assert 'Your Gmail address is not registered in the ERP system' in res.json['message']

    # Confirm user was NOT auto-created in database
    from app.models.user import User
    assert User.query.filter_by(email='stranger@gmail.com').first() is None


def test_google_auth_inactive_account_denied(client, seeded_db, monkeypatch):
    from app.models.user import User
    from app.extensions import db
    user = User.query.filter_by(email='student@test.local').first()
    user.is_active = False
    db.session.commit()

    import requests
    class MockResp:
        status_code = 200
        headers = {'content-type': 'application/json'}
        def json(self):
            return {
                'users': [{
                    'localId': 'mock_fb_uid_inactive',
                    'email': 'student@test.local',
                    'emailVerified': True,
                    'providerUserInfo': [{'providerId': 'google.com'}]
                }]
            }

    monkeypatch.setattr(requests, 'post', lambda *args, **kwargs: MockResp())

    res = client.post('/api/auth/google', json={'id_token': 'inactive_token'})
    assert res.status_code == 403
    assert 'inactive' in res.json['message'].lower()


def test_google_auth_unverified_email_denied(client, seeded_db, monkeypatch):
    import requests
    class MockResp:
        status_code = 200
        headers = {'content-type': 'application/json'}
        def json(self):
            return {
                'users': [{
                    'localId': 'mock_fb_uid_unverified',
                    'email': 'student@test.local',
                    'emailVerified': False,
                    'providerUserInfo': []
                }]
            }

    monkeypatch.setattr(requests, 'post', lambda *args, **kwargs: MockResp())

    res = client.post('/api/auth/google', json={'id_token': 'unverified_token'})
    assert res.status_code == 403
    assert 'not verified' in res.json['message'].lower()


def test_google_auth_spoofed_client_email_ignored(client, seeded_db, monkeypatch):
    """Client sends fake email in body, but server uses verified email from token."""
    import requests
    class MockResp:
        status_code = 200
        headers = {'content-type': 'application/json'}
        def json(self):
            return {
                'users': [{
                    'localId': 'mock_fb_uid_student',
                    'email': 'student@test.local',
                    'emailVerified': True,
                    'providerUserInfo': [{'providerId': 'google.com'}]
                }]
            }

    monkeypatch.setattr(requests, 'post', lambda *args, **kwargs: MockResp())

    # Client tries to claim to be admin in payload
    res = client.post('/api/auth/google', json={
        'id_token': 'valid_student_token',
        'email': 'admin@test.local'
    })
    assert res.status_code == 200
    # Server strictly resolves identity from token email ('student@test.local')
    assert res.json['user']['role'] == 'student'
    assert res.json['user']['email'] == 'student@test.local'


def test_dynamic_email_authorization(client, seeded_db, monkeypatch):
    """Verifies that an unregistered Gmail is denied, but succeeds once added to ERP by Admin."""
    import requests
    class MockResp:
        status_code = 200
        headers = {'content-type': 'application/json'}
        def json(self):
            return {
                'users': [{
                    'localId': 'mock_new_google_user',
                    'email': 'newstudent@gmail.com',
                    'emailVerified': True,
                    'providerUserInfo': [{'providerId': 'google.com'}]
                }]
            }

    monkeypatch.setattr(requests, 'post', lambda *args, **kwargs: MockResp())

    # 1. Before admin creates/adds email: Denied
    res1 = client.post('/api/auth/google', json={'id_token': 'new_token'})
    assert res1.status_code == 401

    # 2. Admin adds user with that email
    from app.models.user import User
    from app.extensions import db
    new_u = User(username='newstudent', email='newstudent@gmail.com', role='student', is_active=True)
    new_u.set_password('Temp@1234')
    db.session.add(new_u)
    db.session.commit()

    # 3. Next Google login: Immediately succeeds without app rebuild
    res2 = client.post('/api/auth/google', json={'id_token': 'new_token'})
    assert res2.status_code == 200
    assert res2.json['success'] is True
    assert res2.json['user']['email'] == 'newstudent@gmail.com'


