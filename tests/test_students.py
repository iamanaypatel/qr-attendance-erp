from app.models.student import Student
from app.models.department import Department

def test_student_crud_and_validation(client, seeded_db):
    # Log in as Admin
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})

    dept = Department.query.filter_by(code='CSE').first()

    # 1. Create Student
    resp = client.post('/admin/students/create', data={
        'student_id': 'STU2026999',
        'full_name': 'Test New Student',
        'email': 'new.student@example.com',
        'department_id': dept.id,
        'course': 'B.Tech CSE',
        'semester': '1st',
        'section': 'A',
        'roll_number': 'CS999',
        'gender': 'Female',
        'create_user_account': 'y'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Test New Student' in resp.data

    student = Student.query.filter_by(student_id='STU2026999').first()
    assert student is not None
    assert student.qr_token is not None
    assert student.user is not None # portal account created

    # 2. Prevent Duplicate student_id
    dup_resp = client.post('/admin/students/create', data={
        'student_id': 'STU2026999',
        'full_name': 'Duplicate Attempt',
        'email': 'different.email@example.com',
        'department_id': dept.id,
        'course': 'B.Tech CSE',
        'semester': '1st',
        'roll_number': 'CS999-2',
        'gender': 'Male'
    }, follow_redirects=True)
    assert b'already registered' in dup_resp.data

    # 3. Edit Student
    edit_resp = client.post(f'/admin/students/{student.id}/edit', data={
        'student_id': 'STU2026999',
        'full_name': 'Test Student Edited Name',
        'email': 'new.student@example.com',
        'department_id': dept.id,
        'course': 'B.Tech CSE',
        'semester': '2nd',
        'section': 'B',
        'roll_number': 'CS999',
        'gender': 'Female'
    }, follow_redirects=True)
    assert edit_resp.status_code == 200
    assert b'Test Student Edited Name' in edit_resp.data

    # 4. Profile View
    profile_resp = client.get(f'/admin/students/{student.id}')
    assert profile_resp.status_code == 200
    assert b'Test Student Edited Name' in profile_resp.data

    # 5. QR Code PNG Download
    qr_resp = client.get(f'/admin/students/{student.id}/qr.png')
    assert qr_resp.status_code == 200
    assert qr_resp.headers['Content-Type'] == 'image/png'

    # 6. ID Card PDF Download
    pdf_resp = client.get(f'/admin/students/{student.id}/id-card.pdf')
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers['Content-Type'] == 'application/pdf'
    assert len(pdf_resp.data) > 500

    # 7. Delete Student
    del_resp = client.post(f'/admin/students/{student.id}/delete', follow_redirects=True)
    assert del_resp.status_code == 200
    assert Student.query.filter_by(student_id='STU2026999').first() is None
