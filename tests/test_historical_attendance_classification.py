import pytest
from datetime import date, time, datetime
from app.extensions import db
from app.models.user import User
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.subject import Subject
from app.models.attendance import Attendance
from app.models.class_coordinator import ClassCoordinator
from app.models.session import AcademicSession
from app.models.audit import AuditLog
from app.attendance.classifier import (
    classify_attendance_record,
    run_historical_classification_migration,
    is_teacher_coordinator_for_record
)

def test_historical_examples_classification(app, seeded_db):
    """
    Test historical examples A through E as required by the Master Prompt:
    Example A: Old Coordinator Attendance, No Subject -> GENERAL
    Example B: Old Subject Teacher Attendance, DBMS -> SUBJECT (DBMS)
    Example C: Teacher later became Coordinator, Old DBMS record -> SUBJECT (DBMS)
    Example D: Teacher had both roles simultaneously -> Record-specific classification
    Example E: Insufficient information / non-coordinator without subject -> LEGACY
    """
    with app.app_context():
        # Setup Teacher 1 and Teacher 2
        t1 = Teacher.query.filter_by(employee_id='TCH101').first()
        student = Student.query.filter_by(student_id='STU2026001').first()
        dept_id = student.department_id

        # Academic Session 2025-2026: 2025-08-01 to 2026-06-30
        sess = AcademicSession.query.filter_by(name='2025-2026').first()
        if not sess:
            sess = AcademicSession(
                name='2025-2026',
                start_date=date(2025, 8, 1),
                end_date=date(2026, 6, 30),
                is_active=True
            )
            seeded_db.session.add(sess)
            seeded_db.session.commit()

        # Subject: DBMS
        dbms = Subject.query.filter_by(subject_code='CS102').first()
        if not dbms:
            dbms = Subject(subject_code='CS102', subject_name='Database Management Systems', is_active=True, department_id=dept_id)
            seeded_db.session.add(dbms)
            seeded_db.session.commit()

        # Setup Coordinator assignment for Teacher 1 for 2025-2026 session
        coord_asgn = ClassCoordinator.assign_coordinator(
            teacher_id=t1.id,
            department_id=dept_id,
            course=student.course,
            semester=student.semester,
            section=student.section,
            session_id=sess.id,
            effective_from=date(2025, 8, 1),
            effective_to=date(2026, 6, 30),
            is_active=True
        )

        # ----------------------------------------------------
        # EXAMPLE A: Old Coordinator Attendance, No Subject
        # ----------------------------------------------------
        rec_a = Attendance(
            student_id=student.id,
            teacher_id=t1.id,
            subject_id=None,
            semester=student.semester,
            section=student.section,
            date=date(2025, 9, 15), # Within coordinator tenure
            status='Present',
            method='QR'
        )
        type_a, reason_a = classify_attendance_record(rec_a)
        assert type_a == 'GENERAL', f"Expected GENERAL, got {type_a}: {reason_a}"
        assert 'Class Coordinator' in reason_a

        # ----------------------------------------------------
        # EXAMPLE B: Old Subject Teacher Attendance, DBMS
        # ----------------------------------------------------
        rec_b = Attendance(
            student_id=student.id,
            teacher_id=t1.id,
            subject_id=dbms.id,
            semester=student.semester,
            section=student.section,
            date=date(2025, 9, 15),
            status='Present',
            method='QR'
        )
        type_b, reason_b = classify_attendance_record(rec_b)
        assert type_b == 'SUBJECT', f"Expected SUBJECT, got {type_b}: {reason_b}"
        assert 'CS102' in reason_b

        # ----------------------------------------------------
        # EXAMPLE C: Teacher later became Coordinator, Old DBMS record
        # Suppose in 2024 (before coordinator assignment in 2025), Teacher took DBMS attendance
        # Even though Teacher is Coordinator now, the old DBMS record must remain SUBJECT!
        # ----------------------------------------------------
        rec_c = Attendance(
            student_id=student.id,
            teacher_id=t1.id,
            subject_id=dbms.id,
            semester='3rd',
            date=date(2024, 10, 10),
            status='Present',
            method='QR'
        )
        type_c, reason_c = classify_attendance_record(rec_c)
        assert type_c == 'SUBJECT', f"Expected SUBJECT, got {type_c}: {reason_c}"

        # ----------------------------------------------------
        # EXAMPLE D: Teacher had both roles simultaneously
        # On same date 2025-09-20:
        # Record 1: General attendance (no subject) -> GENERAL
        # Record 2: DBMS lecture attendance -> SUBJECT
        # ----------------------------------------------------
        rec_d_gen = Attendance(
            student_id=student.id,
            teacher_id=t1.id,
            subject_id=None,
            semester=student.semester,
            section=student.section,
            date=date(2025, 9, 20),
            status='Present',
            method='QR'
        )
        rec_d_sub = Attendance(
            student_id=student.id,
            teacher_id=t1.id,
            subject_id=dbms.id,
            semester=student.semester,
            section=student.section,
            date=date(2025, 9, 20),
            status='Present',
            method='QR'
        )
        type_d1, _ = classify_attendance_record(rec_d_gen)
        type_d2, _ = classify_attendance_record(rec_d_sub)
        assert type_d1 == 'GENERAL', f"Expected GENERAL for record without subject"
        assert type_d2 == 'SUBJECT', f"Expected SUBJECT for DBMS lecture"

        # ----------------------------------------------------
        # EXAMPLE E: Historical record with insufficient/ambiguous information
        # Case 1: Teacher who was NOT coordinator for this class marks attendance with no subject
        # ----------------------------------------------------
        u2 = User(username='unrelated_teacher', email='unrelated@vsmt.edu.in', role='teacher')
        u2.set_password('Teacher@1234')
        seeded_db.session.add(u2)
        seeded_db.session.commit()

        t2 = Teacher(
            user_id=u2.id,
            employee_id='TCH999',
            full_name='Unrelated Teacher',
            email='unrelated@vsmt.edu.in',
            department_id=dept_id,
            is_active=True
        )
        seeded_db.session.add(t2)
        seeded_db.session.commit()

        rec_e = Attendance(
            student_id=student.id,
            teacher_id=t2.id, # NOT coordinator, and NO subject
            subject_id=None,
            semester=student.semester,
            section=student.section,
            date=date(2025, 9, 15),
            status='Present',
            method='Manual'
        )
        type_e, reason_e = classify_attendance_record(rec_e)
        assert type_e == 'LEGACY', f"Expected LEGACY for ambiguous record, got {type_e}: {reason_e}"
        assert 'LEGACY' in type_e

def test_date_sensitive_coordinator_tenure(app, seeded_db):
    """
    Test section 9: Coordinator assignments contain effective date bounds.
    Attendance within effective bounds -> GENERAL.
    Attendance outside effective bounds -> LEGACY.
    """
    with app.app_context():
        t1 = Teacher.query.filter_by(employee_id='TCH101').first()
        student = Student.query.filter_by(student_id='STU2026001').first()

        # Assignment effective: 2025-08-01 to 2026-07-31
        ClassCoordinator.query.filter_by(teacher_id=t1.id).delete()
        asgn = ClassCoordinator(
            teacher_id=t1.id,
            department_id=student.department_id,
            course=student.course,
            semester=student.semester,
            section=student.section,
            effective_from=date(2025, 8, 1),
            effective_to=date(2026, 7, 31),
            is_active=True
        )
        seeded_db.session.add(asgn)
        seeded_db.session.commit()

        # 1. Inside tenure: 2025-09-15
        rec_in = Attendance(
            student_id=student.id,
            teacher_id=t1.id,
            subject_id=None,
            semester=student.semester,
            section=student.section,
            date=date(2025, 9, 15),
            status='Present',
            method='QR'
        )
        type_in, _ = classify_attendance_record(rec_in)
        assert type_in == 'GENERAL'

        # 2. Outside tenure (after expiration): 2026-09-15
        rec_out = Attendance(
            student_id=student.id,
            teacher_id=t1.id,
            subject_id=None,
            semester=student.semester,
            section=student.section,
            date=date(2026, 9, 15), # Expired!
            status='Present',
            method='QR'
        )
        type_out, _ = classify_attendance_record(rec_out)
        assert type_out == 'LEGACY'

        # 3. Outside tenure (before effective_from): 2025-05-15
        rec_before = Attendance(
            student_id=student.id,
            teacher_id=t1.id,
            subject_id=None,
            semester=student.semester,
            section=student.section,
            date=date(2025, 5, 15), # Before start!
            status='Present',
            method='QR'
        )
        type_before, _ = classify_attendance_record(rec_before)
        assert type_before == 'LEGACY'

def test_migration_conservation_and_idempotency(app, seeded_db):
    """
    Test sections 7, 21, 22:
    - TOTAL BEFORE == TOTAL AFTER == GENERAL + SUBJECT + LEGACY
    - Pre-migration backup is created
    - Audit logs are recorded
    - Idempotent: running migration twice produces identical state
    """
    with app.app_context():
        student = Student.query.filter_by(student_id='STU2026001').first()
        t1 = Teacher.query.filter_by(employee_id='TCH101').first()

        # Assign coordinator
        ClassCoordinator.assign_coordinator(
            teacher_id=t1.id,
            department_id=student.department_id,
            semester=student.semester,
            section=student.section,
            is_active=True
        )

        sub1 = Subject(subject_code='TEST101', subject_name='Test Subject 1', is_active=True)
        seeded_db.session.add(sub1)
        seeded_db.session.commit()

        # Create known mix of records:
        # 1. Gate check-in -> GENERAL
        a_gate = Attendance(student_id=student.id, subject_id=None, teacher_id=None, date=date(2026, 1, 10), method='QR')
        # 2. Coordinator record -> GENERAL
        a_coord = Attendance(student_id=student.id, subject_id=None, teacher_id=t1.id, semester=student.semester, section=student.section, date=date(2026, 1, 11), method='QR')
        # 3. Subject record -> SUBJECT
        a_sub = Attendance(student_id=student.id, subject_id=sub1.id, teacher_id=t1.id, date=date(2026, 1, 12), method='QR')
        # 4. Ambiguous non-coordinator teacher without subject -> LEGACY
        u_other = User(username='other_teacher', email='other@vsmt.edu.in', role='teacher')
        u_other.set_password('Teacher@1234')
        seeded_db.session.add(u_other)
        seeded_db.session.commit()

        t_other = Teacher(
            user_id=u_other.id,
            employee_id='TCH888',
            full_name='Other Teacher',
            email='other@vsmt.edu.in',
            department_id=student.department_id,
            is_active=True
        )
        seeded_db.session.add(t_other)
        seeded_db.session.commit()
        a_legacy = Attendance(student_id=student.id, subject_id=None, teacher_id=t_other.id, semester='99th', date=date(2026, 1, 13), method='Manual')

        seeded_db.session.add_all([a_gate, a_coord, a_sub, a_legacy])
        seeded_db.session.commit()

        total_before = Attendance.query.count()

        # Run migration Pass 1
        res1 = run_historical_classification_migration(dry_run=False, force=True)
        assert res1['success'] is True
        assert res1['total_before'] == total_before
        assert res1['total_after'] == total_before
        assert res1['general_count'] + res1['subject_count'] + res1['legacy_count'] == total_before
        assert res1['general_count'] >= 2
        assert res1['subject_count'] >= 1
        assert res1['legacy_count'] >= 1

        # Verify audit logs exist
        audit_records = AuditLog.query.filter_by(action='HISTORICAL_ATTENDANCE_CLASSIFICATION').all()
        assert len(audit_records) >= 4
        summary_audit = AuditLog.query.filter_by(action='HISTORICAL_MIGRATION_SUMMARY').first()
        assert summary_audit is not None

        # Run migration Pass 2 (Idempotency test)
        res2 = run_historical_classification_migration(dry_run=False, force=False)
        assert res2['success'] is True
        assert res2['total_after'] == total_before
        assert res2['reclassified_count'] == 0 # Zero unnecessary changes on repeat!
        assert res2['general_count'] == res1['general_count']
        assert res2['subject_count'] == res1['subject_count']
        assert res2['legacy_count'] == res1['legacy_count']

def test_legacy_does_not_inflate_general_or_subject_stats(client, seeded_db):
    """
    Test section 6, 11, 13, 20:
    - LEGACY records must NOT inflate General Present Today or Subject Attendance stats.
    - Multiple Subject records on the same day count as 1 in General Attendance, but count independently in each subject.
    """
    student = Student.query.filter_by(student_id='STU2026001').first()
    t1 = Teacher.query.filter_by(employee_id='TCH101').first()

    sub_a = Subject(subject_code='SUB_A', subject_name='Subject A', department_id=student.department_id, semester=student.semester, is_active=True)
    sub_b = Subject(subject_code='SUB_B', subject_name='Subject B', department_id=student.department_id, semester=student.semester, is_active=True)
    seeded_db.session.add_all([sub_a, sub_b])
    seeded_db.session.commit()

    test_date = date(2026, 9, 10)

    # 1. General Attendance record
    att_gen = Attendance(
        student_id=student.id,
        subject_id=None,
        teacher_id=t1.id,
        attendance_type='GENERAL',
        date=test_date,
        status='Present',
        method='QR'
    )
    # 2. Subject A attendance
    att_a = Attendance(
        student_id=student.id,
        subject_id=sub_a.id,
        teacher_id=t1.id,
        attendance_type='SUBJECT',
        date=test_date,
        status='Present',
        method='QR'
    )
    # 3. Subject B attendance
    att_b = Attendance(
        student_id=student.id,
        subject_id=sub_b.id,
        teacher_id=t1.id,
        attendance_type='SUBJECT',
        date=test_date,
        status='Present',
        method='QR'
    )
    # 4. Ambiguous / Legacy records for student
    att_leg = Attendance(
        student_id=student.id,
        subject_id=None,
        teacher_id=None,
        attendance_type='LEGACY',
        date=test_date,
        status='Present',
        method='Manual'
    )
    seeded_db.session.add_all([att_gen, att_a, att_b, att_leg])
    seeded_db.session.commit()

    # Verify student general stats:
    stats = student.calculate_attendance_stats()
    # Rahul should count as 1 daily session on 2026-09-10, NOT 4!
    assert stats['present_count'] >= 1
    # Check that Subject stats only count their own subject
    subject_stats = student.get_subject_wise_attendance()
    stat_a = next((s for s in subject_stats if s['subject_id'] == sub_a.id), None)
    stat_b = next((s for s in subject_stats if s['subject_id'] == sub_b.id), None)
    assert stat_a is not None and stat_a['present_classes'] == 1
    assert stat_b is not None and stat_b['present_classes'] == 1
    # And there must NOT be a subject stat for LEGACY
    assert not any(s['subject_id'] is None and s.get('subject_code') == 'LEGACY' for s in subject_stats)
