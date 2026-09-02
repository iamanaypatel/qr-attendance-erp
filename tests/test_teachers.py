from app.models.teacher import Teacher
from app.models.department import Department

def test_teacher_crud_and_validation(client, seeded_db):
    # Log in as Admin
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})

    dept = Department.query.filter_by(code='CSE').first()

    # 1. Create Teacher
    resp = client.post('/admin/teachers/create', data={
        'employee_id': 'TCH999',
        'full_name': 'Prof. Grace Hopper',
        'email': 'grace.hopper@example.com',
        'department_id': dept.id,
        'designation': 'Professor',
        'is_active': 'y',
        'password': 'GracePassword@123'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Prof. Grace Hopper' in resp.data

    teacher = Teacher.query.filter_by(employee_id='TCH999').first()
    assert teacher is not None
    assert teacher.user is not None
    assert teacher.user.role == 'teacher'

    # 2. Prevent duplicate employee ID
    dup_resp = client.post('/admin/teachers/create', data={
        'employee_id': 'TCH999',
        'full_name': 'Duplicate Person',
        'email': 'different.teacher@example.com',
        'department_id': dept.id,
        'designation': 'Lecturer'
    }, follow_redirects=True)
    assert b'already registered' in dup_resp.data

    # 3. Edit Teacher
    edit_resp = client.post(f'/admin/teachers/{teacher.id}/edit', data={
        'employee_id': 'TCH999',
        'full_name': 'Admiral Grace Hopper',
        'email': 'grace.hopper@test.local',
        'department_id': dept.id,
        'designation': 'Distinguished Professor',
        'is_active': 'y'
    }, follow_redirects=True)
    assert edit_resp.status_code == 200
    assert b'Admiral Grace Hopper' in edit_resp.data

    # 4. Delete Teacher
    del_resp = client.post(f'/admin/teachers/{teacher.id}/delete', follow_redirects=True)
    assert del_resp.status_code == 200
    assert Teacher.query.filter_by(employee_id='TCH999').first() is None
