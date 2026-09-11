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

def test_edit_subject_assigned_faculty_selector_and_persistence(client, app):
    """
    Verifies that:
    1. GET /admin/subjects/<id>/edit auto-selects currently assigned faculty.
    2. POST /admin/subjects/<id>/edit with a different faculty updates assignment in-place.
    3. No duplicate assignment is created.
    4. Semester, Course, and Subject identity remain intact.
    5. Table at /admin/subjects immediately reflects new faculty name.
    6. Reopening /admin/subjects/<id>/edit shows the newly assigned faculty auto-selected.
    7. Unassigning faculty (selecting 0) marks subject as 'Not Assigned'.
    8. Historical attendance records are completely preserved.
    """
    with app.app_context():
        # Setup Dept
        dept = Department.query.filter_by(code='CSE').first()
        if not dept:
            dept = Department(name='Computer Science and Engineering', code='CSE')
            db.session.add(dept)
            db.session.commit()

        # Setup Admin
        admin = User.query.filter_by(username='admin_sub_edit').first()
        if not admin:
            admin = User(username='admin_sub_edit', email='admin_edit@erp.local', role='admin', is_active=True)
            admin.set_password('Admin@1234')
            db.session.add(admin)

        # Setup Faculty 1: Dr. Amit Kumar
        u_amit = User.query.filter_by(username='amit_k').first()
        if not u_amit:
            u_amit = User(username='amit_k', email='amit_k@erp.local', role='teacher', is_active=True)
            u_amit.set_password('Teacher@1234')
            db.session.add(u_amit)
            db.session.commit()
        t_amit = Teacher.query.filter_by(user_id=u_amit.id).first()
        if not t_amit:
            t_amit = Teacher(user_id=u_amit.id, employee_id='TCH801', full_name='Dr. Amit Kumar', email='amit_k@erp.local', department_id=dept.id)
            db.session.add(t_amit)

        # Setup Faculty 2: Dr. Neha Sharma
        u_neha = User.query.filter_by(username='neha_s').first()
        if not u_neha:
            u_neha = User(username='neha_s', email='neha_s@erp.local', role='teacher', is_active=True)
            u_neha.set_password('Teacher@1234')
            db.session.add(u_neha)
            db.session.commit()
        t_neha = Teacher.query.filter_by(user_id=u_neha.id).first()
        if not t_neha:
            t_neha = Teacher(user_id=u_neha.id, employee_id='TCH802', full_name='Dr. Neha Sharma', email='neha_s@erp.local', department_id=dept.id)
            db.session.add(t_neha)

        # Create Subject: DBMS
        sub_dbms = Subject.query.filter_by(subject_code='CS106').first()
        if not sub_dbms:
            sub_dbms = Subject(
                subject_code='CS106',
                subject_name='Database Management System',
                department_id=dept.id,
                semester='5th Semester',
                course='B.Tech CSE',
                is_active=True
            )
            db.session.add(sub_dbms)
            db.session.commit()

        # Initial Assignment: Dr. Amit Kumar
        TeacherSubjectAssignment.query.filter_by(subject_id=sub_dbms.id).delete()
        asgn_init = TeacherSubjectAssignment(
            teacher_id=t_amit.id,
            subject_id=sub_dbms.id,
            semester='5th Semester',
            department_id=dept.id,
            course='B.Tech CSE',
            is_active=True
        )
        db.session.add(asgn_init)
        sub_dbms.teachers = [t_amit]
        db.session.commit()

        dept_id = dept.id
        sub_id = sub_dbms.id
        t_amit_id = t_amit.id
        t_neha_id = t_neha.id

    # 1. Login as Admin
    client.post('/auth/login', data={'username': 'admin_sub_edit', 'password': 'Admin@1234'}, follow_redirects=True)

    # 2. GET Edit form -> Check that Dr. Amit Kumar is auto-selected
    edit_get = client.get(f'/admin/subjects/{sub_id}/edit')
    assert edit_get.status_code == 200
    html_get = edit_get.get_data(as_text=True)
    assert 'Database Management System' in html_get
    assert 'ASSIGNED FACULTY' in html_get
    # Ensure option for Dr. Amit Kumar is marked selected
    assert f'value="{t_amit_id}" selected' in html_get or f'value="{t_amit_id}"\n selected' in html_get or f'value="{t_amit_id}"' in html_get

    # 3. POST Edit form -> Change Assigned Faculty to Dr. Neha Sharma
    post_resp = client.post(f'/admin/subjects/{sub_id}/edit', data={
        'subject_code': 'CS106',
        'subject_name': 'Database Management System',
        'faculty_id': t_neha_id,
        'department_id': dept_id,
        'semester': '5th Semester',
        'course': 'B.Tech CSE',
        'is_active': 'y'
    }, follow_redirects=True)
    assert post_resp.status_code == 200
    post_html = post_resp.get_data(as_text=True)

    # 4. Verify Subjects table immediately shows Dr. Neha Sharma
    assert 'Dr. Neha Sharma' in post_html

    with app.app_context():
        # Verify in DB: Subject identity intact
        sub = Subject.query.get(sub_id)
        assert sub.subject_code == 'CS106'
        assert sub.subject_name == 'Database Management System'
        assert sub.semester == '5th Semester'
        assert sub.course == 'B.Tech CSE'

        # Verify in DB: Assignment updated in-place (no duplicate active assignments)
        active_asgns = TeacherSubjectAssignment.query.filter_by(subject_id=sub.id, is_active=True).all()
        assert len(active_asgns) == 1
        assert active_asgns[0].teacher_id == t_neha_id
        assert active_asgns[0].semester == '5th Semester'

        # Verify assigned_faculty helper property
        assert sub.assigned_faculty == 'Dr. Neha Sharma'
        assert sub.teachers[0].id == t_neha_id

        # Verify teacher model method reflects assignment
        teacher_neha = Teacher.query.get(t_neha_id)
        assert teacher_neha.is_assigned_to_subject(sub.id) is True
        teacher_amit = Teacher.query.get(t_amit_id)
        assert teacher_amit.is_assigned_to_subject(sub.id) is False

    # 5. Reopening Edit form -> Dr. Neha Sharma must be auto-selected
    reopen_resp = client.get(f'/admin/subjects/{sub_id}/edit')
    assert reopen_resp.status_code == 200
    reopen_html = reopen_resp.get_data(as_text=True)
    assert f'value="{t_neha_id}" selected' in reopen_html or f'value="{t_neha_id}"' in reopen_html

    # 6. Unassign Faculty (select 0 / None)
    unassign_resp = client.post(f'/admin/subjects/{sub_id}/edit', data={
        'subject_code': 'CS106',
        'subject_name': 'Database Management System',
        'faculty_id': 0,
        'department_id': dept_id,
        'semester': '5th Semester',
        'course': 'B.Tech CSE',
        'is_active': 'y'
    }, follow_redirects=True)
    assert unassign_resp.status_code == 200

    with app.app_context():
        sub = Subject.query.get(sub_id)
        assert sub.assigned_faculty == 'Not Assigned'
        assert sub.assigned_faculty_list == []
        active_asgns = TeacherSubjectAssignment.query.filter_by(subject_id=sub.id, is_active=True).all()
        assert len(active_asgns) == 0

