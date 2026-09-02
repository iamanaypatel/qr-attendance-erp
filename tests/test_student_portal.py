def test_student_portal_views_and_downloads(client, seeded_db):
    # Log in as Student
    client.post('/auth/login', data={'identity': 'student', 'password': 'Student@1234'})

    # 1. Dashboard
    dash_resp = client.get('/student/dashboard')
    assert dash_resp.status_code == 200
    assert b'Student Portal' in dash_resp.data

    # 2. Profile
    prof_resp = client.get('/student/profile')
    assert prof_resp.status_code == 200
    assert b'My Student Profile' in prof_resp.data

    # 3. QR Code View & Download
    qr_view_resp = client.get('/student/qr-code')
    assert qr_view_resp.status_code == 200
    assert b'Attendance QR Code' in qr_view_resp.data

    qr_dl_resp = client.get('/student/qr-code/download')
    assert qr_dl_resp.status_code == 200
    assert qr_dl_resp.headers['Content-Type'] == 'image/png'

    # 4. History View
    hist_resp = client.get('/student/history')
    assert hist_resp.status_code == 200
    assert b'Attendance History' in hist_resp.data

    # 5. ID Card View & PDF Download
    id_card_resp = client.get('/student/id-card')
    assert id_card_resp.status_code == 200
    assert b'Digital Student Identity Card' in id_card_resp.data

    id_pdf_resp = client.get('/student/id-card/download')
    assert id_pdf_resp.status_code == 200
    assert id_pdf_resp.headers['Content-Type'] == 'application/pdf'
    assert id_pdf_resp.data.startswith(b'%PDF')

    # 6. Restricted Access Check (Student cannot access admin routes)
    admin_access_resp = client.get('/admin/students', follow_redirects=False)
    assert admin_access_resp.status_code == 302
    assert '/student/dashboard' in admin_access_resp.headers['Location']
