import pytest
from datetime import date, timedelta
from app.extensions import db
from app.models.user import User
from app.models.teacher import Teacher
from app.models.subject import Subject
from app.models.subject_assignment import TeacherSubjectAssignment
from app.models.student import Student
from app.models.department import Department
from app.models.attendance import Attendance

def test_assigned_faculty_display_single_and_multiple(app):
    """
    Verifies that Assigned Faculty displays actual faculty name from TeacherSubjectAssignment,
    handles multiple assignments cleanly, and handles unassigned subjects without error.
    """
    with app.app_context():
        # Setup Department
        dept = Department.query.filter_by(code='CSE').first()
        if not dept:
            dept = Department(name='Computer Science and Engineering', code='CSE')
            db.session.add(dept)
            db.session.commit()

        # Setup 2 Teachers
        user1 = User.query.filter_by(username='prof_amit').first()
        if not user1:
            user1 = User(username='prof_amit', email='amit@erp.local', role='teacher')
            user1.set_password('Password123!')
            db.session.add(user1)
            db.session.commit()
        teacher1 = Teacher.query.filter_by(user_id=user1.id).first()
        if not teacher1:
            teacher1 = Teacher(user_id=user1.id, employee_id='TCH901', full_name='Dr. Amit Kumar', email='amit@erp.local')
            db.session.add(teacher1)
            db.session.commit()

        user2 = User.query.filter_by(username='prof_neha').first()
        if not user2:
            user2 = User(username='prof_neha', email='neha@erp.local', role='teacher')
            user2.set_password('Password123!')
            db.session.add(user2)
            db.session.commit()
        teacher2 = Teacher.query.filter_by(user_id=user2.id).first()
        if not teacher2:
            teacher2 = Teacher(user_id=user2.id, employee_id='TCH902', full_name='Dr. Neha Sharma', email='neha@erp.local')
            db.session.add(teacher2)
            db.session.commit()

        # 1. Subject with 1 assigned faculty
        sub_wt = Subject.query.filter_by(subject_code='TEST_WT101').first()
        if not sub_wt:
            sub_wt = Subject(subject_code='TEST_WT101', subject_name='Web Technology', department_id=dept.id, semester='5th')
            db.session.add(sub_wt)
            db.session.commit()

        # Clear existing assignments for idempotency
        TeacherSubjectAssignment.query.filter_by(subject_id=sub_wt.id).delete()
        db.session.commit()

        asgn1 = TeacherSubjectAssignment(
            teacher_id=teacher1.id,
            subject_id=sub_wt.id,
            semester='5th Semester',
            department_id=dept.id,
            is_active=True
        )
        db.session.add(asgn1)
        db.session.commit()

        # Verify single assignment
        assert sub_wt.assigned_faculty == 'Dr. Amit Kumar'
        assert len(sub_wt.assigned_faculty_list) == 1
        assert sub_wt.assigned_faculty_list[0]['name'] == 'Dr. Amit Kumar'
        assert sub_wt.assigned_faculty_list[0]['teacher_id'] == teacher1.id

        # 2. Subject with multiple assignments across semesters
        sub_dbms = Subject.query.filter_by(subject_code='TEST_DBMS101').first()
        if not sub_dbms:
            sub_dbms = Subject(subject_code='TEST_DBMS101', subject_name='DBMS', department_id=dept.id, semester='4th')
            db.session.add(sub_dbms)
            db.session.commit()

        TeacherSubjectAssignment.query.filter_by(subject_id=sub_dbms.id).delete()
        db.session.commit()

        asgn_dbms_1 = TeacherSubjectAssignment(
            teacher_id=teacher1.id,
            subject_id=sub_dbms.id,
            semester='4th Semester',
            department_id=dept.id,
            is_active=True
        )
        asgn_dbms_2 = TeacherSubjectAssignment(
            teacher_id=teacher2.id,
            subject_id=sub_dbms.id,
            semester='6th Semester',
            department_id=dept.id,
            is_active=True
        )
        db.session.add_all([asgn_dbms_1, asgn_dbms_2])
        db.session.commit()

        dbms_faculties = sub_dbms.assigned_faculty_list
        assert len(dbms_faculties) == 2
        faculty_names = [f['name'] for f in dbms_faculties]
        assert 'Dr. Amit Kumar' in faculty_names
        assert 'Dr. Neha Sharma' in faculty_names
        assert 'None' not in faculty_names
        assert 'Not Assigned' not in faculty_names

        # 3. Subject with no assignment
        sub_unassigned = Subject.query.filter_by(subject_code='TEST_UNASSIGNED').first()
        if not sub_unassigned:
            sub_unassigned = Subject(subject_code='TEST_UNASSIGNED', subject_name='Quantum Computing', department_id=dept.id)
            db.session.add(sub_unassigned)
            db.session.commit()

        TeacherSubjectAssignment.query.filter_by(subject_id=sub_unassigned.id).delete()
        sub_unassigned.teachers = []
        db.session.commit()

        assert sub_unassigned.assigned_faculty == 'Not Assigned'
        assert sub_unassigned.assigned_faculty_list == []
        assert sub_unassigned.total_sessions == 0


def test_day_based_total_sessions_strict_deduplication(app):
    """
    Verifies that:
    1. 1 class day with 5, 20, or 50 students = 1 session.
    2. Multiple scans for same student (Time In + Time Out) = 1 session.
    3. Duplicate scans = 1 session.
    4. Next day = next session (2 distinct dates = 2 sessions).
    5. 5 class dates = 5 sessions.
    6. General Attendance on the same date does NOT increase Subject Total Sessions.
    7. Multiple subjects conducted on same date maintain independent session counts (1 each).
    """
    with app.app_context():
        # Setup Department & Subject
        dept = Department.query.filter_by(code='CSE').first()
        if not dept:
            dept = Department(name='Computer Science and Engineering', code='CSE')
            db.session.add(dept)
            db.session.commit()

        sub_ds = Subject.query.filter_by(subject_code='TEST_DS501').first()
        if not sub_ds:
            sub_ds = Subject(subject_code='TEST_DS501', subject_name='Data Structures Lab', department_id=dept.id)
            db.session.add(sub_ds)
            db.session.commit()

        sub_os = Subject.query.filter_by(subject_code='TEST_OS502').first()
        if not sub_os:
            sub_os = Subject(subject_code='TEST_OS502', subject_name='Operating Systems Lab', department_id=dept.id)
            db.session.add(sub_os)
            db.session.commit()

        # Clean existing test attendances
        Attendance.query.filter(Attendance.subject_id.in_([sub_ds.id, sub_os.id])).delete()
        db.session.commit()

        assert sub_ds.total_sessions == 0
        assert sub_os.total_sessions == 0

        # Create 5 test students
        students = []
        for i in range(1, 6):
            s = Student.query.filter_by(student_id=f'TEST_STU_{i}').first()
            if not s:
                s = Student(
                    student_id=f'TEST_STU_{i}',
                    roll_number=f'ROLL_TEST_{i}',
                    full_name=f'Student Number {i}',
                    department_id=dept.id,
                    semester='4th Semester',
                    course='B.Tech',
                    qr_token=f'QR_TEST_TOKEN_{i}',
                    is_active=True
                )
                db.session.add(s)
                db.session.commit()
            students.append(s)

        # SCENARIO 1: Day 1 (2026-09-11) - 5 students scanned for Data Structures
        day1 = date(2026, 9, 11)
        for s in students:
            att = Attendance(
                student_id=s.id,
                subject_id=sub_ds.id,
                date=day1,
                attendance_type='SUBJECT',
                status='Present'
            )
            db.session.add(att)
        db.session.commit()

        # Total Sessions must be 1 (NOT 5)
        assert sub_ds.total_sessions == 1

        # SCENARIO 2: General Attendance taken on the same date for all 5 students
        for s in students:
            gen_att = Attendance(
                student_id=s.id,
                subject_id=None,
                date=day1,
                attendance_type='GENERAL',
                status='Present'
            )
            db.session.add(gen_att)
        db.session.commit()

        # General attendance must NOT increase Subject total sessions
        assert sub_ds.total_sessions == 1

        # SCENARIO 3: OS Lab also conducted on Day 1 for 3 students
        for s in students[:3]:
            att_os = Attendance(
                student_id=s.id,
                subject_id=sub_os.id,
                date=day1,
                attendance_type='SUBJECT',
                status='Present'
            )
            db.session.add(att_os)
        db.session.commit()

        # OS sessions = 1, DS sessions = 1 (no cross-contamination)
        assert sub_ds.total_sessions == 1
        assert sub_os.total_sessions == 1

        # SCENARIO 4: Next class days for Data Structures (12 Sep, 15 Sep, 16 Sep, 18 Sep)
        other_days = [
            date(2026, 9, 12),
            date(2026, 9, 15),
            date(2026, 9, 16),
            date(2026, 9, 18),
        ]
        for d in other_days:
            for s in students:
                att = Attendance(
                    student_id=s.id,
                    subject_id=sub_ds.id,
                    date=d,
                    attendance_type='SUBJECT',
                    status='Present'
                )
                db.session.add(att)
        db.session.commit()

        # Now Data Structures has 5 distinct days: 11, 12, 15, 16, 18 Sep
        # Total student rows in database = 25
        # Total Sessions MUST be 5 (NOT 25)
        assert sub_ds.attendances.count() == 25
        assert sub_ds.total_sessions == 5

        # OS was only conducted on 11 Sep, so OS total_sessions remains 1
        assert sub_os.total_sessions == 1

        # SCENARIO 5: to_dict exposes total_sessions correctly
        d = sub_ds.to_dict()
        assert d['total_sessions'] == 5
        assert d['attendance_count'] == 5
        assert d['historical_records_count'] == 25

def test_admin_subjects_page_html_and_api_day_based_sessions(client, app):
    """
    Verifies that:
    1. /admin/subjects HTML table displays faculty names (e.g. Dr. Amit Kumar).
    2. /admin/subjects HTML table displays day-based Total Sessions count (2 dates with 10 records = 2 sessions).
    3. /api/teacher/subjects returns day-based total_sessions = 2.
    """
    with app.app_context():
        # Setup Department
        dept = Department.query.filter_by(code='CSE').first()
        if not dept:
            dept = Department(name='Computer Science and Engineering', code='CSE')
            db.session.add(dept)
            db.session.commit()

        # Admin user
        admin = User(username='admin_test_view', email='admin_view@erp.local', role='admin', is_active=True)
        admin.set_password('Admin@1234')
        db.session.add(admin)

        # Teacher user
        t_user = User(username='teacher_amit', email='amit_view@erp.local', role='teacher', is_active=True)
        t_user.set_password('Teacher@1234')
        db.session.add(t_user)
        db.session.commit()

        teacher = Teacher(
            user_id=t_user.id,
            employee_id='TCH999',
            full_name='Dr. Amit Kumar',
            email='amit_view@erp.local',
            department_id=dept.id
        )
        db.session.add(teacher)
        db.session.commit()

        # Subject
        sub = Subject(
            subject_code='CS999',
            subject_name='Distributed Cloud Systems',
            department_id=dept.id,
            semester='6th Semester',
            is_active=True
        )
        db.session.add(sub)
        db.session.commit()

        # Assignment
        asgn = TeacherSubjectAssignment(
            teacher_id=teacher.id,
            subject_id=sub.id,
            semester='6th Semester',
            department_id=dept.id,
            is_active=True
        )
        db.session.add(asgn)
        db.session.commit()

        # Students & Attendance on 2 distinct dates
        day1 = date(2026, 9, 11)
        day2 = date(2026, 9, 12)
        for i in range(1, 6):
            stu = Student(
                student_id=f'STU_DAY_{i}',
                roll_number=f'ROLL_DAY_{i}',
                full_name=f'Student {i}',
                department_id=dept.id,
                course='B.Tech',
                semester='6th Semester',
                qr_token=f'QR_TOKEN_{i}'
            )
            db.session.add(stu)
            db.session.flush()

            # Day 1 attendance
            db.session.add(Attendance(
                student_id=stu.id,
                subject_id=sub.id,
                teacher_id=teacher.id,
                date=day1,
                attendance_type='SUBJECT',
                status='Present'
            ))
            # Day 2 attendance
            db.session.add(Attendance(
                student_id=stu.id,
                subject_id=sub.id,
                teacher_id=teacher.id,
                date=day2,
                attendance_type='SUBJECT',
                status='Present'
            ))
        db.session.commit()

        # 10 attendance records exist for this subject across 2 distinct dates
        assert sub.attendances.count() == 10
        assert sub.total_sessions == 2

    # Login as Admin
    client.post('/auth/login', data={
        'username': 'admin_test_view',
        'password': 'Admin@1234'
    }, follow_redirects=True)

    # 1. Admin Subjects page
    resp = client.get('/admin/subjects')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # Confirm Subject and Assigned Faculty appear
    assert 'CS999' in html
    assert 'Distributed Cloud Systems' in html
    assert 'Dr. Amit Kumar' in html
    # Confirm Total Sessions renders as 2 (not 10)
    assert '<span class="fw-bold font-mono">2</span>' in html

    # 2. API /api/teacher/subjects
    api_resp = client.get('/api/teacher/subjects')
    assert api_resp.status_code == 200
    data = api_resp.get_json()
    assert data.get('success') is True
    assert 'subjects' in data
    matching_sub = next((s for s in data['subjects'] if s['code'] == 'CS999'), None)
    assert matching_sub is not None
    assert matching_sub['teacher_name'] == 'Dr. Amit Kumar'
    assert matching_sub['total_sessions'] == 2
    assert matching_sub['total_classes'] == 2
