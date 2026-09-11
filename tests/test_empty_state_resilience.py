import pytest
from app import create_app
from app.extensions import db
from app.models.user import User

def test_empty_database_routes_resilience():
    """Verify that all management pages render safely without 500 error on an empty database."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        # Only admin user exists
        admin = User(username='admin', email='admin@test.local', role='admin', is_active=True)
        admin.set_password('Admin@1234')
        db.session.add(admin)
        db.session.commit()

        client = app.test_client()
        client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})

        empty_routes = [
            '/admin/dashboard',
            '/admin/students',
            '/admin/teachers',
            '/admin/subjects',
            '/admin/subject-assignments',
            '/admin/class-coordinators',
            '/admin/settings',
            '/admin/departments',
            '/admin/qr-generator',
            '/attendance/calendar',
            '/attendance/manual',
            '/attendance/scanner',
            '/reports/',
            '/reports/print',
        ]

        for path in empty_routes:
            resp = client.get(path)
            assert resp.status_code == 200, f"Failed on path {path} with status {resp.status_code}"

        # Test empty API stats
        token = admin.generate_auth_token()
        resp_stats = client.get('/api/dashboard/stats', headers={'Authorization': f'Bearer {token}'})
        assert resp_stats.status_code == 200
        stats = resp_stats.get_json()
        assert stats.get('total_students') == 0
        assert stats.get('present_today') == 0

        db.session.remove()
        db.drop_all()
