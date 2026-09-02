def test_app_creation(app):
    assert app is not None
    assert app.config['TESTING'] is True

def test_api_health(client):
    response = client.get('/api/health')
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['status'] == 'healthy'
    assert 'QR Attendance ERP' in json_data['system']

def test_root_redirect_to_login(client):
    response = client.get('/', follow_redirects=False)
    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']
