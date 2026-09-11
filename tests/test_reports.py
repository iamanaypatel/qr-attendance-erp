from datetime import date, timedelta
from app.extensions import db
from app.models.attendance import Attendance
from app.models.student import Student
from app.models.user import User


def test_reports_access_and_filters(client, seeded_db):
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})
    resp = client.get('/reports/')
    assert resp.status_code == 200
    assert b'Attendance Reports' in resp.data


def test_reports_pagination_duplicate_page_fix(client, app, seeded_db):
    """
    Verify pagination when moving between Page 1, Page 2, Page 3 with active filters:
    - Page 2 must not raise TypeError (Context.call() got multiple values for keyword argument 'page')
    - Active filters (e.g. status=Present, type=GENERAL) must be preserved in pagination links
    - Boundary states: Page 1 Previous disabled; Page 3 Next disabled
    - Page appears exactly once in generated URLs
    """
    with app.app_context():
        student = Student.query.first()
        today = date.today()
        # Seed 45 attendance records to create 3 pages (20 per page)
        for i in range(45):
            att = Attendance(
                student_id=student.id,
                date=today - timedelta(days=i),
                attendance_type='GENERAL',
                status='Present'
            )
            db.session.add(att)
        db.session.commit()

    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})

    # 1. Page 1 test with query filters
    resp_p1 = client.get('/reports/?status=Present&type=GENERAL')
    assert resp_p1.status_code == 200
    data_p1 = resp_p1.data.decode('utf-8')
    assert 'Attendance Reports' in data_p1
    # Page 1 Previous should be disabled
    assert '<li class="page-item disabled"><span class="page-link">Previous</span></li>' in data_p1
    # Next link must contain page=2 and preserved filters
    assert 'page=2' in data_p1
    assert 'status=Present' in data_p1
    assert 'type=GENERAL' in data_p1

    # 2. Page 2 test (the exact previous failure scenario)
    resp_p2 = client.get('/reports/?page=2&status=Present&type=GENERAL')
    assert resp_p2.status_code == 200
    data_p2 = resp_p2.data.decode('utf-8')
    # Previous link must exist and link to page=1
    assert 'page=1' in data_p2
    # Next link must exist and link to page=3
    assert 'page=3' in data_p2
    # No duplicate 'page=' parameter in generated URLs
    assert 'page=2&amp;page=' not in data_p2
    assert 'page=1&amp;page=' not in data_p2
    assert 'page=3&amp;page=' not in data_p2

    # 3. Page 3 test (boundary / last page)
    resp_p3 = client.get('/reports/?page=3&status=Present&type=GENERAL')
    assert resp_p3.status_code == 200
    data_p3 = resp_p3.data.decode('utf-8')
    # Previous link must exist and link to page=2
    assert 'page=2' in data_p3
    # Next link on last page should be disabled
    assert '<li class="page-item disabled"><span class="page-link">Next</span></li>' in data_p3


def test_reports_teacher_role_access(client, seeded_db):
    """Teachers should also be able to view and paginate reports."""
    client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})
    resp = client.get('/reports/?page=1')
    assert resp.status_code == 200
    assert b'Attendance Reports' in resp.data


def test_reports_student_role_forbidden(client, seeded_db):
    """Students should be forbidden from accessing reports (redirected with access denied)."""
    client.post('/auth/login', data={'identity': 'student', 'password': 'Student@1234'})
    resp = client.get('/reports/')
    # Web role_required redirects unauthorized users to their dashboard
    assert resp.status_code == 302
    assert '/student/' in resp.headers.get('Location', '')


def test_export_excel(client, seeded_db):
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})
    resp = client.get('/reports/export/excel?type=GENERAL')
    assert resp.status_code == 200
    assert resp.headers['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    assert len(resp.data) > 500


def test_export_pdf(client, seeded_db):
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})
    resp = client.get('/reports/export/pdf?type=GENERAL')
    assert resp.status_code == 200
    assert resp.headers['Content-Type'] == 'application/pdf'
    assert resp.data.startswith(b'%PDF')


def test_export_csv(client, seeded_db):
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})
    resp = client.get('/reports/export/csv?type=GENERAL')
    assert resp.status_code == 200
    assert 'text/csv' in resp.headers['Content-Type']
    assert b'Student ID,Student Name,Department' in resp.data


def test_print_view(client, seeded_db):
    client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})
    resp = client.get('/reports/print?type=GENERAL')
    assert resp.status_code == 200
    assert b'OFFICIAL ATTENDANCE REPORT' in resp.data
