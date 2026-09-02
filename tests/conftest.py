import pytest
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.department import Department
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.session import AcademicSession

@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def seeded_db(app):
    with app.app_context():
        dept = Department(name='Computer Science', code='CSE')
        db.session.add(dept)
        db.session.commit()

        # Admin
        admin = User(username='admin', email='admin@test.local', role='admin', is_active=True)
        admin.set_password('Admin@1234')
        db.session.add(admin)

        # Teacher
        teacher_u = User(username='teacher', email='teacher@test.local', role='teacher', is_active=True)
        teacher_u.set_password('Teacher@1234')
        db.session.add(teacher_u)
        db.session.commit()

        teacher = Teacher(
            user_id=teacher_u.id,
            employee_id='TCH101',
            full_name='Dr. Test Teacher',
            email='teacher@test.local',
            department_id=dept.id
        )
        db.session.add(teacher)

        # Student
        student_u = User(username='student', email='student@test.local', role='student', is_active=True)
        student_u.set_password('Student@1234')
        db.session.add(student_u)
        db.session.commit()

        student = Student(
            user_id=student_u.id,
            student_id='STU2026001',
            full_name='Alice Smith',
            email='student@test.local',
            department_id=dept.id,
            course='B.Tech CSE',
            semester='4th',
            roll_number='CS01',
            qr_token=Student.generate_qr_token()
        )
        db.session.add(student)
        db.session.commit()
        yield db
