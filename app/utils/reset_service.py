import os
import json
from datetime import datetime, date
from app.extensions import db
from app.models.user import User
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.attendance import Attendance
from app.models.holiday import Holiday
from app.models.session import AcademicSession
from app.models.subject import Subject, teacher_subjects
from app.models.subject_assignment import TeacherSubjectAssignment
from app.models.class_coordinator import ClassCoordinator
from app.models.audit import AuditLog
from app.utils.timezone import get_current_ist_time

MODE_ATTENDANCE = 'ATTENDANCE'
MODE_OPERATIONAL = 'OPERATIONAL'
MODE_FACTORY = 'FACTORY'

VALID_MODES = (MODE_ATTENDANCE, MODE_OPERATIONAL, MODE_FACTORY)


def get_reset_preview(reset_type: str) -> dict:
    """
    Returns live database counts and scope descriptions for the selected reset mode.
    """
    norm_type = (reset_type or '').strip().upper()
    if norm_type not in VALID_MODES:
        norm_type = MODE_ATTENDANCE

    att_count = Attendance.query.count()
    stu_count = Student.query.count()
    tch_count = Teacher.query.count()
    asgn_count = TeacherSubjectAssignment.query.count()
    
    # Secondary table count
    try:
        sec_asgn_count = len(db.session.execute(teacher_subjects.select()).all())
    except Exception:
        sec_asgn_count = 0
        
    coord_count = ClassCoordinator.query.count()
    sub_count = Subject.query.count()
    hol_count = Holiday.query.count()
    sess_count = AcademicSession.query.count()
    
    # Non-admin users count
    non_admin_users = User.query.filter(User.role != 'admin').count()

    preview = {
        'reset_type': norm_type,
        'attendance_count': att_count,
        'students_count': stu_count,
        'teachers_count': tch_count,
        'assignments_count': asgn_count + sec_asgn_count,
        'coordinators_count': coord_count,
        'subjects_count': sub_count,
        'holidays_count': hol_count,
        'sessions_count': sess_count,
        'non_admin_users_count': non_admin_users
    }

    if norm_type == MODE_ATTENDANCE:
        preview['total_affected'] = att_count
        preview['title'] = 'Reset Attendance Data'
        preview['scope_description'] = 'Removes all historical attendance records, Time In / Time Out timestamps, and session logs.'
        preview['preserved_description'] = 'Preserves all Students, Teachers, Subjects, Assignments, Class Coordinators, Sessions, and Admin accounts.'
        preview['requires_password'] = False
    elif norm_type == MODE_OPERATIONAL:
        preview['total_affected'] = att_count + stu_count + tch_count + asgn_count + sec_asgn_count + coord_count + hol_count
        preview['title'] = 'Reset Operational ERP Data'
        preview['scope_description'] = 'Clears student and teacher rosters, user accounts, attendance, subject assignments, coordinators, and holidays.'
        preview['preserved_description'] = 'Preserves Master Subjects, Academic Sessions, Departments, Institution Settings, and Admin accounts.'
        preview['requires_password'] = True
    else: # FACTORY
        preview['total_affected'] = att_count + stu_count + tch_count + asgn_count + sec_asgn_count + coord_count + sub_count + hol_count + non_admin_users
        preview['title'] = 'Full Factory Reset'
        preview['scope_description'] = 'Completely clears all ERP data including subjects, assignments, student/teacher accounts, and attendance to return to a clean initial installation.'
        preview['preserved_description'] = 'Preserves Primary Super Admin account and resets core institution settings and default session so system is ready to use immediately.'
        preview['requires_password'] = True

    return preview


def create_reset_snapshot(reset_type: str, admin_user) -> str:
    """
    Creates a pre-reset JSON snapshot file before executing destructive row deletion.
    Returns the file path.
    """
    try:
        backup_dir = os.path.join(os.getcwd(), 'instance', 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        now_str = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"reset_snapshot_{reset_type.lower()}_{now_str}.json"
        filepath = os.path.join(backup_dir, filename)

        preview = get_reset_preview(reset_type)

        snapshot_data = {
            'snapshot_timestamp_utc': datetime.utcnow().isoformat(),
            'snapshot_timestamp_ist': get_current_ist_time().isoformat(),
            'reset_type': reset_type,
            'initiated_by_admin_id': admin_user.id if admin_user else None,
            'initiated_by_admin_username': admin_user.username if admin_user else 'Unknown',
            'affected_record_counts': preview
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(snapshot_data, f, indent=2)

        return filepath
    except Exception as e:
        # If filesystem backup fails, return a descriptor string but don't fail transaction
        return f"snapshot_error: {str(e)}"


def execute_reset(reset_type: str, admin_user, ip_address: str = None) -> tuple[bool, dict, str]:
    """
    Executes row-level reset inside an atomic database transaction.
    Respects foreign-key dependencies:
    Attendance -> Assignments/Coordinators -> Students/Teachers -> Users -> Subjects -> Sessions
    NEVER drops database tables or schemas.
    Always preserves or guarantees Super Admin access.
    
    Returns (success: bool, deleted_counts: dict, message_or_error: str)
    """
    norm_type = (reset_type or '').strip().upper()
    if norm_type not in VALID_MODES:
        return False, {}, f"Invalid reset mode: '{reset_type}'"

    # 1. Create pre-reset backup snapshot
    snapshot_path = create_reset_snapshot(norm_type, admin_user)

    deleted_counts = {}

    try:
        # Atomic transaction
        # Step 1: ALWAYS delete attendance records first
        att_del = Attendance.query.delete(synchronize_session=False)
        deleted_counts['attendances'] = att_del

        # Step 2: For Operational & Factory, delete assignments, coordinators, holidays, students, teachers
        if norm_type in (MODE_OPERATIONAL, MODE_FACTORY):
            try:
                tc_del = db.session.execute(teacher_subjects.delete()).rowcount
            except Exception:
                tc_del = 0
            asgn_del = TeacherSubjectAssignment.query.delete(synchronize_session=False)
            coord_del = ClassCoordinator.query.delete(synchronize_session=False)
            hol_del = Holiday.query.delete(synchronize_session=False)

            deleted_counts['teacher_subjects'] = tc_del
            deleted_counts['teacher_subject_assignments'] = asgn_del
            deleted_counts['class_coordinators'] = coord_del
            deleted_counts['holidays'] = hol_del

            # Collect linked student and teacher user IDs
            stu_users = [s.user_id for s in Student.query.with_entities(Student.user_id).all() if s.user_id]
            tch_users = [t.user_id for t in Teacher.query.with_entities(Teacher.user_id).all() if t.user_id]

            stu_del = Student.query.delete(synchronize_session=False)
            tch_del = Teacher.query.delete(synchronize_session=False)

            deleted_counts['students'] = stu_del
            deleted_counts['teachers'] = tch_del

            # Delete linked users, strictly protecting all admin accounts
            admin_ids = {u.id for u in User.query.filter_by(role='admin').all()}
            u_ids_to_del = set(stu_users + tch_users) - admin_ids
            if u_ids_to_del:
                u_del = User.query.filter(User.id.in_(u_ids_to_del)).delete(synchronize_session=False)
                deleted_counts['users_student_teacher'] = u_del

        # Step 3: For Factory, also delete subjects, remaining non-admin users, and reset session
        if norm_type == MODE_FACTORY:
            sub_del = Subject.query.delete(synchronize_session=False)
            deleted_counts['subjects'] = sub_del

            non_admin_u_del = User.query.filter(User.role != 'admin').delete(synchronize_session=False)
            deleted_counts['non_admin_users'] = non_admin_u_del

            # Reset academic sessions to single default active session
            AcademicSession.query.delete(synchronize_session=False)
            default_session = AcademicSession(
                name='2025-2026',
                start_date=date(2025, 8, 1),
                end_date=date(2026, 6, 30),
                is_active=True
            )
            db.session.add(default_session)
            deleted_counts['academic_sessions_reset'] = 1

        # Post-reset verification: Ensure affected tables are genuinely clean
        if Attendance.query.count() != 0:
            raise RuntimeError("Verification error: Attendance records remain in database after deletion.")

        if norm_type in (MODE_OPERATIONAL, MODE_FACTORY):
            if Student.query.count() != 0 or Teacher.query.count() != 0:
                raise RuntimeError("Verification error: Student or Teacher records remain in database.")
            if TeacherSubjectAssignment.query.count() != 0:
                raise RuntimeError("Verification error: Subject assignments remain in database.")
            if ClassCoordinator.query.count() != 0:
                raise RuntimeError("Verification error: Class coordinators remain in database.")

        if norm_type == MODE_FACTORY:
            if Subject.query.count() != 0:
                raise RuntimeError("Verification error: Subject definitions remain in database.")

        # Ensure active Admin user is protected and exists
        current_admin = None
        if admin_user and admin_user.id:
            current_admin = User.query.get(admin_user.id)
        if not current_admin:
            # Fallback: ensure at least one active admin exists
            any_admin = User.query.filter_by(role='admin').first()
            if not any_admin:
                super_admin = User(username='admin', email='admin@vsmt.edu.in', role='admin', is_active=True)
                super_admin.set_password('Admin@1234')
                db.session.add(super_admin)

        db.session.commit()

        total_rows = sum(v for v in deleted_counts.values() if isinstance(v, int))
        success_msg = f"{norm_type} reset executed successfully. {total_rows} records removed."

        # Audit log
        AuditLog.log(
            action=f"RESET_{norm_type}",
            details=f"Admin {admin_user.username if admin_user else 'system'} executed {norm_type} reset. {total_rows} records cleared. Snapshot: {os.path.basename(snapshot_path)}",
            user_id=admin_user.id if admin_user else None
        )

        return True, deleted_counts, success_msg

    except Exception as e:
        db.session.rollback()
        AuditLog.log(
            action=f"RESET_{norm_type}_FAILED",
            details=f"Admin {admin_user.username if admin_user else 'system'} attempted {norm_type} reset: {str(e)}",
            user_id=admin_user.id if admin_user else None
        )
        return False, {}, f"Reset operation aborted and rolled back: {str(e)}"
