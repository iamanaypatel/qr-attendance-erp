def test_reports_access_and_filters(client, seeded_db):
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})
    resp = client.get('/reports/')
    assert resp.status_code == 200
    assert b'Attendance Reports' in resp.data

def test_export_excel(client, seeded_db):
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})
    resp = client.get('/reports/export/excel')
    assert resp.status_code == 200
    assert resp.headers['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    assert len(resp.data) > 500

def test_export_pdf(client, seeded_db):
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})
    resp = client.get('/reports/export/pdf')
    assert resp.status_code == 200
    assert resp.headers['Content-Type'] == 'application/pdf'
    assert resp.data.startswith(b'%PDF')

def test_export_csv(client, seeded_db):
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})
    resp = client.get('/reports/export/csv')
    assert resp.status_code == 200
    assert 'text/csv' in resp.headers['Content-Type']
    assert b'Student ID,Student Name,Department' in resp.data

def test_print_view(client, seeded_db):
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})
    resp = client.get('/reports/print')
    assert resp.status_code == 200
    assert b'OFFICIAL ATTENDANCE REPORT' in resp.data
