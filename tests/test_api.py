from app.models.student import Student

def test_api_health_endpoint(client):
    resp = client.get('/api/health')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'healthy'
    assert 'V2.0' in data['system']

def test_api_students_and_stats(client, seeded_db):
    # Log in as Teacher
    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})

    # Test /api/dashboard/stats
    stats_resp = client.get('/api/dashboard/stats')
    assert stats_resp.status_code == 200
    stats_data = stats_resp.get_json()
    assert stats_data['success'] is True
    assert 'total_students' in stats_data
    assert 'present_today' in stats_data

    # Test /api/students
    stu_resp = client.get('/api/students')
    assert stu_resp.status_code == 200
    stu_data = stu_resp.get_json()
    assert stu_data['success'] is True
    assert stu_data['count'] > 0

    first_student_id = stu_data['students'][0]['id']

    # Test /api/students/<id>
    detail_resp = client.get(f'/api/students/{first_student_id}')
    assert detail_resp.status_code == 200
    detail_data = detail_resp.get_json()
    assert detail_data['success'] is True
    assert 'stats' in detail_data['student']

    # Test /api/attendance/today
    today_resp = client.get('/api/attendance/today')
    assert today_resp.status_code == 200
    today_data = today_resp.get_json()
    assert today_data['success'] is True
