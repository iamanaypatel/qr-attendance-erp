def test_teacher_portal_views(client, seeded_db):
    # Log in as Teacher
    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})

    # 1. Teacher Dashboard
    dash_resp = client.get('/teacher/dashboard')
    assert dash_resp.status_code == 200
    assert b'Teacher Portal' in dash_resp.data

    # 2. Teacher Students List
    stu_resp = client.get('/teacher/students')
    assert stu_resp.status_code == 200
    assert b'Department Students' in stu_resp.data

    # 3. Restricted Access Check (Teacher cannot access admin settings)
    admin_resp = client.get('/admin/settings', follow_redirects=False)
    assert admin_resp.status_code == 302
    assert '/teacher/dashboard' in admin_resp.headers['Location']
