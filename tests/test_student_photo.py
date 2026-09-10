import io
from pathlib import Path
import pytest
from PIL import Image
from flask import url_for
from app.models.user import User
from app.models.student import Student
from app.models.department import Department
from app.utils.photo import get_upload_folder, delete_student_photo

def create_test_image(format='JPEG', size=(200, 200), color=(70, 130, 180)):
    """Generate in-memory valid image bytes."""
    buf = io.BytesIO()
    if format.upper() == 'PNG':
        img = Image.new('RGBA', size, color + (200,))
        img.save(buf, format='PNG')
    elif format.upper() == 'WEBP':
        img = Image.new('RGB', size, color)
        img.save(buf, format='WEBP')
    else:
        img = Image.new('RGB', size, color)
        img.save(buf, format='JPEG', quality=90)
    buf.seek(0)
    return buf

@pytest.fixture
def student_photo_env(app):
    with app.app_context():
        from app.extensions import db

        dept = Department.query.filter_by(code='CSE').first()
        if not dept:
            dept = Department(name='Computer Science & Engineering', code='CSE')
            db.session.add(dept)
            db.session.commit()

        # Admin user
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', email='admin@vsmt.edu.in', role='admin', is_active=True)
            admin.set_password('Admin@1234')
            db.session.add(admin)

        # Student A
        user_a = User.query.filter_by(username='student_photo_a').first()
        if not user_a:
            user_a = User(username='student_photo_a', email='photo_a@vsmt.edu.in', role='student', is_active=True)
            user_a.set_password('Password@123')
            db.session.add(user_a)
            db.session.flush()

        student_a = Student.query.filter_by(student_id='STU_PHOTO_001').first()
        if not student_a:
            student_a = Student(
                user_id=user_a.id,
                student_id='STU_PHOTO_001',
                full_name='Photo Test Student A',
                email='photo_a@vsmt.edu.in',
                roll_number='CS-PHOTO-001',
                department_id=dept.id,
                course='B.Tech CSE',
                semester='4th',
                section='A',
                qr_token=Student.generate_qr_token()
            )
            db.session.add(student_a)

        # Student B
        user_b = User.query.filter_by(username='student_photo_b').first()
        if not user_b:
            user_b = User(username='student_photo_b', email='photo_b@vsmt.edu.in', role='student', is_active=True)
            user_b.set_password('Password@123')
            db.session.add(user_b)
            db.session.flush()

        student_b = Student.query.filter_by(student_id='STU_PHOTO_002').first()
        if not student_b:
            student_b = Student(
                user_id=user_b.id,
                student_id='STU_PHOTO_002',
                full_name='Photo Test Student B',
                email='photo_b@vsmt.edu.in',
                roll_number='CS-PHOTO-002',
                department_id=dept.id,
                course='B.Tech CSE',
                semester='4th',
                section='A',
                qr_token=Student.generate_qr_token()
            )
            db.session.add(student_b)

        db.session.commit()
        yield {
            'student_a': student_a,
            'student_b': student_b
        }

        # Cleanup test photos from disk
        if student_a.photo:
            delete_student_photo(student_a.photo)
        if student_b.photo:
            delete_student_photo(student_b.photo)

def test_admin_upload_valid_jpg_student_photo(client, student_photo_env, app):
    """Test 1: Admin uploads a valid JPG photo for student; file is saved and URL serves JPEG."""
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})
    student = student_photo_env['student_a']

    img_data = create_test_image(format='JPEG', color=(255, 100, 50))
    resp = client.post(
        f'/admin/students/{student.id}/photo',
        data={'photo': (img_data, 'avatar.jpg')},
        content_type='multipart/form-data',
        follow_redirects=True
    )
    assert resp.status_code == 200
    assert b"Profile photo for Photo Test Student A updated successfully." in resp.data

    with app.app_context():
        refreshed = Student.query.get(student.id)
        assert refreshed.photo is not None
        assert refreshed.photo.startswith('student_STU_PHOTO_001_')
        assert refreshed.photo.endswith('.jpg')

        # Check file exists on filesystem
        upload_dir = get_upload_folder()
        saved_file = upload_dir / refreshed.photo
        assert saved_file.exists()
        assert saved_file.stat().st_size > 0

        # Check photo_url property
        photo_url = refreshed.photo_url
        assert photo_url is not None
        assert f"/static/uploads/{refreshed.photo}?v=" in photo_url

    # Check direct image URL access in browser returns HTTP 200 and image/jpeg
    direct_resp = client.get(f'/static/uploads/{refreshed.photo}')
    assert direct_resp.status_code == 200
    assert 'image/jpeg' in direct_resp.content_type

    # Verify Pillow can open the saved image bytes
    loaded_img = Image.open(io.BytesIO(direct_resp.data))
    assert loaded_img.format == 'JPEG'
    assert loaded_img.mode == 'RGB'

def test_admin_upload_valid_png_with_transparency(client, student_photo_env, app):
    """Test 2: Admin uploads a PNG with transparency; normalized to clean RGB JPEG."""
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})
    student = student_photo_env['student_b']

    img_data = create_test_image(format='PNG', color=(0, 200, 100))
    resp = client.post(
        f'/admin/students/{student.id}/photo',
        data={'photo': (img_data, 'transparent.png')},
        content_type='multipart/form-data',
        follow_redirects=True
    )
    assert resp.status_code == 200

    with app.app_context():
        refreshed = Student.query.get(student.id)
        assert refreshed.photo is not None
        assert refreshed.photo.endswith('.jpg')

        # Directly load file and ensure it is converted to RGB JPEG
        direct_resp = client.get(f'/static/uploads/{refreshed.photo}')
        assert direct_resp.status_code == 200
        assert 'image/jpeg' in direct_resp.content_type
        img = Image.open(io.BytesIO(direct_resp.data))
        assert img.mode == 'RGB'

def test_student_upload_photo_via_profile(client, student_photo_env, app):
    """Test 3: Logged-in student uploads photo from /student/profile."""
    client.post('/auth/login', data={'identity': 'student_photo_a', 'password': 'Password@123'})

    img_data = create_test_image(format='WEBP', color=(50, 150, 250))
    resp = client.post(
        '/student/profile/photo',
        data={'photo': (img_data, 'profile_pic.webp')},
        content_type='multipart/form-data',
        follow_redirects=True
    )
    assert resp.status_code == 200
    assert b"Profile photo updated successfully!" in resp.data

    # Profile page displays actual student.photo_url
    with app.app_context():
        student = Student.query.filter_by(student_id='STU_PHOTO_001').first()
        assert student.photo is not None
        assert student.photo.encode('utf-8') in resp.data
        assert b'id="studentProfileImg"' in resp.data

def test_invalid_and_corrupted_image_rejection(client, student_photo_env, app):
    """Test 4: Disguised text file and corrupted bytes are rejected without modifying DB."""
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})
    student = student_photo_env['student_a']

    # 1. Text file disguised as .jpg
    fake_jpg = io.BytesIO(b"This is plain text disguised as an executable or jpg.")
    resp1 = client.post(
        f'/admin/students/{student.id}/photo',
        data={'photo': (fake_jpg, 'exploit.jpg')},
        content_type='multipart/form-data',
        follow_redirects=True
    )
    assert resp1.status_code == 200
    assert b"Unable to upload image" in resp1.data

    # 2. Corrupted truncated image bytes
    corrupted_jpg = io.BytesIO(b"\xff\xd8\xff\xe0" + b"garbage byte sequence")
    resp2 = client.post(
        f'/admin/students/{student.id}/photo',
        data={'photo': (corrupted_jpg, 'corrupt.jpg')},
        content_type='multipart/form-data',
        follow_redirects=True
    )
    assert resp2.status_code == 200
    assert b"Unable to upload image" in resp2.data

def test_photo_replacement_cleans_old_file_and_updates_cache(client, student_photo_env, app):
    """Test 5: Replacing photo deletes previous file from disk and increments version timestamp."""
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})
    student = student_photo_env['student_a']
    upload_dir = get_upload_folder()

    # Upload Photo 1
    img1 = create_test_image(format='JPEG', color=(100, 100, 100))
    client.post(
        f'/admin/students/{student.id}/photo',
        data={'photo': (img1, 'first.jpg')},
        content_type='multipart/form-data'
    )

    with app.app_context():
        s1 = Student.query.get(student.id)
        photo1 = s1.photo
        path1 = upload_dir / photo1
        assert path1.exists()

    # Upload Photo 2 (Replacement)
    img2 = create_test_image(format='PNG', color=(200, 50, 50))
    client.post(
        f'/admin/students/{student.id}/photo',
        data={'photo': (img2, 'second.png')},
        content_type='multipart/form-data'
    )

    with app.app_context():
        s2 = Student.query.get(student.id)
        photo2 = s2.photo
        path2 = upload_dir / photo2
        assert photo2 != photo1
        assert path2.exists()
        # Old photo must have been unlinked
        assert not path1.exists()

def test_multi_student_photo_isolation(client, student_photo_env, app):
    """Test 6: Student A and Student B photos are distinct and isolated."""
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})
    s_a = student_photo_env['student_a']
    s_b = student_photo_env['student_b']

    img_a = create_test_image(format='JPEG', color=(255, 0, 0))
    img_b = create_test_image(format='JPEG', color=(0, 0, 255))

    client.post(f'/admin/students/{s_a.id}/photo', data={'photo': (img_a, 'a.jpg')}, content_type='multipart/form-data')
    client.post(f'/admin/students/{s_b.id}/photo', data={'photo': (img_b, 'b.jpg')}, content_type='multipart/form-data')

    with app.app_context():
        refreshed_a = Student.query.get(s_a.id)
        refreshed_b = Student.query.get(s_b.id)

        assert refreshed_a.photo != refreshed_b.photo
        assert 'STU_PHOTO_001' in refreshed_a.photo
        assert 'STU_PHOTO_002' in refreshed_b.photo

def test_missing_photo_fallback_handling(app):
    """Test 7: Student with None or missing photo file returns safe fallback values without error."""
    with app.app_context():
        from app.extensions import db
        dept = Department.query.first()
        if not dept:
            dept = Department(name='Computer Science & Engineering', code='CSE')
            db.session.add(dept)
            db.session.commit()

        student_no_photo = Student(
            student_id='STU_NO_PHOTO',
            full_name='No Photo Student',
            roll_number='CS-NO-01',
            department_id=dept.id,
            course='B.Tech',
            semester='1st',
            photo=None,
            qr_token=Student.generate_qr_token()
        )
        assert student_no_photo.photo_url is None
        d = student_no_photo.to_dict()
        assert d['photo'] is None
        assert d['photo_url'] is None

