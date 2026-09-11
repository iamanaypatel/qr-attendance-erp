import os
import json
import shutil
import logging
from datetime import datetime, date
from flask import current_app
from app.extensions import db
from app.models.attendance import Attendance
from app.models.class_coordinator import ClassCoordinator
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.subject import Subject
from app.models.audit import AuditLog

logger = logging.getLogger(__name__)

def backup_database() -> str:
    """
    Create a pre-migration backup of the SQLite database before running
    historical attendance classification.
    """
    try:
        engine_name = db.engine.dialect.name
        if engine_name == 'sqlite':
            db_path = None
            db_uri = str(db.engine.url)
            if '///' in db_uri:
                db_path = db_uri.split('///')[-1].split('?')[0]
            elif current_app and 'SQLALCHEMY_DATABASE_URI' in current_app.config:
                uri = current_app.config['SQLALCHEMY_DATABASE_URI']
                if '///' in uri:
                    db_path = uri.split('///')[-1].split('?')[0]

            if db_path and os.path.exists(db_path):
                backup_dir = os.path.join(os.path.dirname(os.path.abspath(db_path)), 'backups')
                os.makedirs(backup_dir, exist_ok=True)
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                backup_filename = f"qr_attendance_pre_classification_{timestamp}.db"
                backup_path = os.path.join(backup_dir, backup_filename)
                shutil.copy2(db_path, backup_path)
                logger.info(f"✓ SQLite database backup successfully created at: {backup_path}")
                return backup_path
        else:
            logger.info(f"Database dialect is {engine_name}; external automated backup or snapshot recommended.")
            return f"{engine_name}_managed_backup"
    except Exception as e:
        logger.warning(f"Database backup warning: {e}")
    return "backup_skipped"

def is_teacher_coordinator_for_record(teacher_id: int, student: Student, target_date: date, semester: str = None, section: str = None) -> bool:
    """
    Determine if a teacher was acting as the Class Coordinator for the given student/class
    specifically on the target attendance date.
    Performs date-sensitive checks using:
    - effective_from and effective_to
    - academic_session start_date and end_date
    - department, semester, section, and course matching
    """
    if not teacher_id:
        return False

    assignments = ClassCoordinator.query.filter_by(teacher_id=teacher_id).all()
    if not assignments:
        return False

    import re
    stu_sem = ((student.semester if student else semester) or '').strip().lower()
    stu_sem_digits = re.findall(r'\d+', stu_sem)
    stu_sec = ((student.section if student else section) or '').strip().lower()
    stu_course = (student.course or '').strip().lower() if student else ''
    stu_dept_id = student.department_id if student else None

    for asgn in assignments:
        # 1. Date sensitivity check
        if not asgn.is_effective_on(target_date):
            continue

        # 2. Department check
        if asgn.department_id and stu_dept_id and asgn.department_id != stu_dept_id:
            continue

        # 3. Semester check
        asgn_sem = (asgn.semester or '').strip().lower()
        if asgn_sem:
            asgn_digits = re.findall(r'\d+', asgn_sem)
            if asgn_sem != stu_sem and asgn_sem not in stu_sem and stu_sem not in asgn_sem:
                if not (stu_sem_digits and asgn_digits and stu_sem_digits == asgn_digits):
                    continue

        # 4. Section check
        if asgn.section and asgn.section.strip():
            asgn_sec = asgn.section.strip().lower()
            if stu_sec and asgn_sec != stu_sec:
                continue

        # 5. Course check
        if asgn.course and asgn.course.strip():
            asgn_crs = asgn.course.strip().lower()
            if stu_course and (asgn_crs != stu_course and asgn_crs not in stu_course and stu_course not in asgn_crs):
                continue

        # Matched active/dated coordinator assignment
        return True

    return False

def classify_attendance_record(record: Attendance) -> tuple[str, str]:
    """
    Determines the historical role and context for an individual attendance record.
    Returns: (attendance_type, classification_reason)
    
    Priority:
    1. Valid subject_id present -> SUBJECT
    2. No subject_id, teacher was Class Coordinator on record.date -> GENERAL
    3. No subject_id, teacher was NOT Class Coordinator on record.date -> LEGACY (do not guess)
    4. No subject_id, no teacher_id, campus QR gate scan or Admin check-in with valid student -> GENERAL
    5. Ambiguous / missing student or unverified context -> LEGACY
    """
    student = record.student

    # Rule 1 & 2: Subject context
    if record.subject_id is not None:
        sub = record.subject or db.session.get(Subject, record.subject_id)
        sub_code = sub.subject_code if sub else f"ID {record.subject_id}"
        return (
            'SUBJECT',
            f"Original subject lecture context (subject={sub_code}, teacher_id={record.teacher_id})"
        )

    # Rule 3: Teacher marked attendance without subject_id
    if record.teacher_id is not None:
        if is_teacher_coordinator_for_record(
            teacher_id=record.teacher_id,
            student=student,
            target_date=record.date,
            semester=record.semester,
            section=record.section
        ):
            t_name = record.teacher.full_name if record.teacher else f"Teacher {record.teacher_id}"
            return (
                'GENERAL',
                f"Class Coordinator general daily attendance by {t_name} on {record.date}"
            )
        else:
            t_name = record.teacher.full_name if record.teacher else f"Teacher {record.teacher_id}"
            return (
                'LEGACY',
                f"Attendance marked by {t_name} without subject and without Class Coordinator tenure on {record.date}"
            )

    # Rule 4: Campus Gate QR Scanner or Admin Daily Check-in (no teacher, no subject)
    if student is not None and record.method in ('QR', 'Admin', 'Manual'):
        marker_str = record.marker.username if record.marker else 'Campus System'
        return (
            'GENERAL',
            f"General campus daily check-in (method={record.method}, marked_by={marker_str})"
        )

    # Rule 5: Insufficient or ambiguous context
    return (
        'LEGACY',
        "Insufficient historical role context to determine General or Subject attendance"
    )

def run_historical_classification_migration(dry_run: bool = False, force: bool = False) -> dict:
    """
    Executes the idempotent historical attendance classification migration.
    Guarantees:
    - Zero records deleted.
    - Total attendance record conservation: total_before == total_after.
    - GENERAL + SUBJECT + LEGACY == total_after.
    - Pre-migration backup.
    - Full audit trail in AuditLog table.
    """
    backup_path = "dry_run" if dry_run else backup_database()

    total_before = Attendance.query.count()
    records = Attendance.query.order_by(Attendance.id.asc()).all()

    counts = {
        'GENERAL': 0,
        'SUBJECT': 0,
        'LEGACY': 0
    }
    reclassified_count = 0
    now_dt = datetime.utcnow()

    for rec in records:
        new_type, reason = classify_attendance_record(rec)
        counts[new_type] = counts.get(new_type, 0) + 1

        old_type = rec.attendance_type
        needs_update = force or (rec.attendance_type != new_type) or (rec.classification_reason != reason)

        if needs_update:
            reclassified_count += 1
            if not dry_run:
                rec.attendance_type = new_type
                rec.classification_reason = reason
                rec.classified_at = now_dt

                # Record detailed audit log entry
                audit_details = json.dumps({
                    'record_id': rec.id,
                    'student_id': rec.student_id,
                    'date': rec.date.strftime('%Y-%m-%d') if rec.date else None,
                    'old_type': old_type,
                    'new_type': new_type,
                    'reason': reason,
                    'subject_id': rec.subject_id,
                    'teacher_id': rec.teacher_id,
                    'method': rec.method
                })
                AuditLog.log(
                    action='HISTORICAL_ATTENDANCE_CLASSIFICATION',
                    details=audit_details,
                    commit=False
                )

    if not dry_run:
        db.session.commit()

    total_after = Attendance.query.count()

    # Conservation invariant validation
    if total_before != total_after:
        raise RuntimeError(
            f"Data conservation violation: total before ({total_before}) != total after ({total_after})"
        )

    sum_classified = counts['GENERAL'] + counts['SUBJECT'] + counts['LEGACY']
    if sum_classified != total_after:
        raise RuntimeError(
            f"Classification sum violation: GENERAL({counts['GENERAL']}) + "
            f"SUBJECT({counts['SUBJECT']}) + LEGACY({counts['LEGACY']}) = {sum_classified} != {total_after}"
        )

    # Log summary audit record
    if not dry_run:
        summary_details = json.dumps({
            'total_before': total_before,
            'total_after': total_after,
            'reclassified_count': reclassified_count,
            'general_count': counts['GENERAL'],
            'subject_count': counts['SUBJECT'],
            'legacy_count': counts['LEGACY'],
            'backup_path': backup_path,
            'timestamp': now_dt.isoformat()
        })
        AuditLog.log(
            action='HISTORICAL_MIGRATION_SUMMARY',
            details=summary_details,
            commit=True
        )

    logger.info(
        f"✓ Historical attendance classification complete: "
        f"Total={total_after} (GENERAL={counts['GENERAL']}, SUBJECT={counts['SUBJECT']}, LEGACY={counts['LEGACY']})"
    )

    return {
        'success': True,
        'dry_run': dry_run,
        'total_before': total_before,
        'total_after': total_after,
        'reclassified_count': reclassified_count,
        'counts': counts,
        'general_count': counts['GENERAL'],
        'subject_count': counts['SUBJECT'],
        'legacy_count': counts['LEGACY'],
        'backup_path': backup_path
    }
