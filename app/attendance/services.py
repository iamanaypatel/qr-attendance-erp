from datetime import datetime, date, time
from flask import current_app
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.subject import Subject
from app.models.attendance import Attendance
from app.models.settings import SystemSetting
from app.models.audit import AuditLog
from app.utils.timezone import get_current_ist_date, get_current_ist_time

def process_qr_attendance(token: str, marker_user=None, subject_id=None, semester=None, attendance_type='SUBJECT', **kwargs) -> dict:
    """
    Core business logic for QR code attendance verification and state machine:
    1. Validate token -> Student
    2. Normalize attendance_type ('GENERAL' vs 'SUBJECT')
    3. Validate coordinator authorization (for GENERAL) or subject teacher authorization (for SUBJECT)
    4. Check today's attendance record strictly isolated by attendance_type (and subject_id if SUBJECT)
    5. First scan -> Record Time In (authoritative IST time)
    6. Second scan -> Record Time Out (authoritative IST time, calculated duration)
    7. Subsequent scan -> Informative duplicate warning with timestamps
    """
    if not token or not token.strip():
        return {
            'success': False,
            'message': 'Invalid scan: No QR token provided.'
        }

    token = token.strip()
    student = Student.query.filter_by(qr_token=token).first()
    if not student:
        student = Student.query.filter((Student.student_id == token) | (Student.roll_number == token)).first()

    if not student:
        return {
            'success': False,
            'message': 'Unrecognized QR code. Student not found in system.'
        }

    if not student.is_active:
        return {
            'success': False,
            'message': f"Student {student.full_name} ({student.student_id}) account is inactive."
        }

    # Support teacher/user passed via kwargs or marker_user
    if marker_user is None:
        marker_user = kwargs.get('user') or kwargs.get('teacher')

    # Normalize attendance_type ('GENERAL', 'SUBJECT', or 'COMBINED')
    att_type_clean = (attendance_type or '').strip().upper()
    if att_type_clean == 'COMBINED':
        attendance_type = 'COMBINED'
    elif att_type_clean == 'GENERAL' or (subject_id is None and att_type_clean != 'SUBJECT'):
        attendance_type = 'GENERAL'
        subject_id = None
    else:
        attendance_type = 'SUBJECT'

    # Subject & Teacher / Coordinator Authorization Validation
    subject = None
    teacher_obj = None

    # Identify marker_user role
    is_teacher = False
    is_admin = False
    if isinstance(marker_user, Teacher):
        is_teacher = True
        teacher_obj = marker_user
    else:
        is_teacher = getattr(marker_user, 'is_teacher', False) or getattr(marker_user, 'role', '') == 'teacher'
        is_admin = getattr(marker_user, 'is_admin', False) or getattr(marker_user, 'role', '') == 'admin'

        if is_teacher:
            teacher_obj = getattr(marker_user, 'teacher_profile', None)
            if not teacher_obj and hasattr(marker_user, 'id'):
                teacher_obj = Teacher.query.filter_by(user_id=marker_user.id).first()

        elif is_admin:
            teacher_obj = getattr(marker_user, 'teacher_profile', None)

    teacher_id = teacher_obj.id if teacher_obj else None

    # Handle COMBINED Attendance (Subject + General / Journal)
    if attendance_type == 'COMBINED':
        return _process_combined_qr_attendance(
            student=student,
            marker_user=marker_user,
            teacher_obj=teacher_obj,
            is_teacher=is_teacher,
            is_admin=is_admin,
            subject_id=subject_id,
            semester=semester,
            **kwargs
        )

    # 1. GENERAL ATTENDANCE AUTHORIZATION
    if attendance_type == 'GENERAL':
        if is_teacher:
            if not teacher_obj or not teacher_obj.is_coordinator_for_student(student):
                return {
                    'success': False,
                    'error_code': 'UNAUTHORIZED_COORDINATOR',
                    'action': 'UNAUTHORIZED_COORDINATOR',
                    'message': f"Access Denied: You are not authorized to take General Attendance for {student.full_name} ({student.course or 'Course'}, {student.semester or 'Sem'}, Sec {student.section or 'N/A'}). Only their assigned Class Coordinator can take General Attendance."
                }
        elif not is_admin:
            return {
                'success': False,
                'error_code': 'UNAUTHORIZED',
                'action': 'UNAUTHORIZED',
                'message': 'Unauthorized: Only Class Coordinators and Administrators can take General Attendance.'
            }

    # 2. SUBJECT ATTENDANCE AUTHORIZATION
    else:
        if subject_id is None:
            return {
                'success': False,
                'error_code': 'SUBJECT_REQUIRED',
                'message': 'Subject must be selected for subject-wise attendance.'
            }

        try:
            subject_id = int(subject_id)
        except (ValueError, TypeError):
            return {
                'success': False,
                'message': 'Invalid subject identifier provided.'
            }

        subject = Subject.query.get(subject_id)
        if not subject:
            return {
                'success': False,
                'message': f"Subject with ID {subject_id} does not exist."
            }

        if not subject.is_active:
            return {
                'success': False,
                'message': f"Subject '{subject.subject_name}' ({subject.subject_code}) is currently inactive."
            }

        if is_teacher:
            if not teacher_obj or not teacher_obj.is_assigned_to_subject(subject_id, semester=semester):
                sem_str = f" in {semester}" if semester else ""
                return {
                    'success': False,
                    'error_code': 'UNAUTHORIZED_SUBJECT',
                    'message': f"Access Denied: You are not authorized to take attendance for {subject.subject_name} ({subject.subject_code}){sem_str}."
                }

            # If semester not explicitly passed, try resolving from teacher's active assignment
            if not semester and teacher_obj:
                assignment = teacher_obj.subject_assignments.filter_by(subject_id=subject_id, is_active=True).first()
                if assignment and assignment.semester:
                    semester = assignment.semester

        # Fallback semester if not resolved from assignment
        if not semester and subject:
            semester = subject.semester

    # Authoritative current date and time in Asia/Kolkata (IST = UTC+05:30)
    today = get_current_ist_date()
    now_time = get_current_ist_time()

    # Look up existing record for today strictly scoped by attendance_type:
    # GENERAL: (student_id, date, attendance_type='GENERAL') -> Exactly 1 record per day
    # SUBJECT: (student_id, date, subject_id, attendance_type='SUBJECT') -> 1 record per subject per day
    query = Attendance.query.filter(Attendance.student_id == student.id, Attendance.date == today)
    if attendance_type == 'GENERAL':
        query = query.filter(
            (Attendance.attendance_type == 'GENERAL') |
            (Attendance.attendance_type.is_(None) & Attendance.subject_id.is_(None))
        )
    else:
        query = query.filter(
            Attendance.subject_id == subject_id,
            (Attendance.attendance_type == 'SUBJECT') | (Attendance.subject_id.is_(None))
        )

    record = query.first()
    subject_label = f" in {subject.subject_name}" if (attendance_type == 'SUBJECT' and subject) else " (General Attendance)"

    if not record:
        # Case 1: First scan -> Check In (Time In)
        try:
            record = Attendance(
                student_id=student.id,
                attendance_type=attendance_type,
                subject_id=subject_id if attendance_type == 'SUBJECT' else None,
                teacher_id=teacher_id,
                semester=semester or student.semester,
                section=student.section if student else None,
                date=today,
                time_in=now_time,
                time_out=None,
                status='Present',
                marked_by=marker_user.id if marker_user and hasattr(marker_user, 'id') else None,
                method='QR'
            )
            db.session.add(record)
            db.session.commit()
        except IntegrityError as ie:
            db.session.rollback()
            current_app.logger.warning(f"Integrity warning on check-in: {ie}. Querying existing record...")
            if attendance_type == 'GENERAL':
                record = Attendance.query.filter(
                    Attendance.student_id == student.id,
                    Attendance.date == today,
                    (Attendance.attendance_type == 'GENERAL') | (Attendance.subject_id.is_(None))
                ).first()
            else:
                record = Attendance.query.filter_by(student_id=student.id, date=today, subject_id=subject_id).first()
            if not record:
                return {
                    'success': False,
                    'error_code': 'DATABASE_ERROR',
                    'message': 'Unable to record attendance due to database unique constraint.'
                }
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Unexpected database error saving Time In: {e}")
            return {
                'success': False,
                'error_code': 'SERVER_ERROR',
                'message': f"Failed to save attendance: {str(e)}"
            }

        AuditLog.log(
            'ATTENDANCE_TIME_IN',
            f"Time In ({attendance_type}) for {student.student_id}{subject_label} at {now_time.strftime('%I:%M %p')}",
            user_id=marker_user.id if marker_user and hasattr(marker_user, 'id') else None
        )

        current_app.logger.info(
            f"ATTENDANCE_TIME_IN: Type={attendance_type} Teacher={teacher_id} Subject={subject_id} ({subject.subject_name if subject else 'General'}) "
            f"Semester={semester or student.semester} Student={student.student_id} AttendanceId={record.id}"
        )

        return {
            'success': True,
            'action': 'TIME_IN',
            'attendance_type': attendance_type,
            'message': f"Time In marked successfully for {student.full_name}{subject_label} at {now_time.strftime('%I:%M %p')}.",
            'student': student.to_dict(),
            'subject_id': subject_id,
            'subject': {
                'id': subject.id,
                'code': subject.subject_code,
                'name': subject.subject_name,
                'semester': semester or (subject.semester if subject else None)
            } if subject else None,
            'teacher': {
                'id': teacher_obj.id,
                'name': teacher_obj.full_name
            } if teacher_obj else None,
            'attendance': record.to_dict()
        }

    # Case 2: Record exists, but Time Out has not been marked yet
    if record.time_out is None:
        # Check cooldown to prevent accidental double-tap within seconds
        cooldown = int(SystemSetting.get_setting('duplicate_scan_cooldown_seconds', '30'))
        if record.time_in:
            time_in_dt = datetime.combine(today, record.time_in)
            now_dt = datetime.combine(today, now_time)
            elapsed_seconds = (now_dt - time_in_dt).total_seconds()
            if 0 <= elapsed_seconds < cooldown:
                return {
                    'success': False,
                    'action': 'COOLDOWN',
                    'attendance_type': attendance_type,
                    'message': f"Scan cooldown active: Time In was just recorded {int(elapsed_seconds)}s ago. Please wait.",
                    'student': student.to_dict(),
                    'subject_id': subject_id,
                    'subject': {
                        'id': subject.id,
                        'code': subject.subject_code,
                        'name': subject.subject_name,
                        'semester': record.semester or (subject.semester if subject else None)
                    } if subject else None,
                    'attendance': record.to_dict()
                }

        try:
            record.time_out = now_time
            if teacher_id and not record.teacher_id:
                record.teacher_id = teacher_id
            if semester and not record.semester:
                record.semester = semester
            record.updated_at = datetime.utcnow()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Unexpected database error saving Time Out: {e}")
            return {
                'success': False,
                'error_code': 'SERVER_ERROR',
                'message': f"Failed to save Time Out: {str(e)}"
            }

        AuditLog.log(
            'ATTENDANCE_TIME_OUT',
            f"Time Out ({attendance_type}) for {student.student_id}{subject_label} at {now_time.strftime('%I:%M %p')}",
            user_id=marker_user.id if marker_user and hasattr(marker_user, 'id') else None
        )

        current_app.logger.info(
            f"ATTENDANCE_TIME_OUT: Type={attendance_type} Teacher={teacher_id} Subject={subject_id} ({subject.subject_name if subject else 'General'}) "
            f"Semester={record.semester or semester} Student={student.student_id} AttendanceId={record.id}"
        )

        return {
            'success': True,
            'action': 'TIME_OUT',
            'attendance_type': attendance_type,
            'message': f"Time Out marked successfully for {student.full_name}{subject_label} at {now_time.strftime('%I:%M %p')}.",
            'student': student.to_dict(),
            'subject_id': subject_id,
            'subject': {
                'id': subject.id,
                'code': subject.subject_code,
                'name': subject.subject_name,
                'semester': record.semester or (subject.semester if subject else None)
            } if subject else None,
            'teacher': {
                'id': teacher_obj.id,
                'name': teacher_obj.full_name
            } if teacher_obj else None,
            'attendance': record.to_dict()
        }

    # Case 3: Both Time In and Time Out already completed for today in this subject session
    in_time_fmt = record.time_in.strftime('%I:%M %p') if record.time_in else '-'
    out_time_fmt = record.time_out.strftime('%I:%M %p') if record.time_out else '-'

    current_app.logger.info(
        f"ATTENDANCE_ALREADY_COMPLETED: Type={attendance_type} Teacher={teacher_id} Subject={subject_id} ({subject.subject_name if subject else 'General'}) "
        f"Semester={record.semester or semester} Student={student.student_id} AttendanceId={record.id}"
    )

    return {
        'success': False,
        'action': 'ALREADY_COMPLETED',
        'attendance_type': attendance_type,
        'message': f"Attendance already completed today for {student.full_name}{subject_label} (In: {in_time_fmt}, Out: {out_time_fmt}).",
        'student': student.to_dict(),
        'subject_id': subject_id,
        'subject': {
            'id': subject.id,
            'code': subject.subject_code,
            'name': subject.subject_name,
            'semester': record.semester or (subject.semester if subject else None)
        } if subject else None,
        'attendance': record.to_dict()
    }


def _process_combined_qr_attendance(student, marker_user, teacher_obj, is_teacher, is_admin, subject_id, semester, **kwargs) -> dict:
    """
    Core business logic for Combined QR Attendance (Class Coordinator):
    Simultaneously records both:
    1. GENERAL Attendance (subject_id=None, attendance_type='GENERAL')
    2. SUBJECT Attendance (subject_id=subject_id, attendance_type='SUBJECT')
    in a single atomic transaction with independent state machines and cross-type isolation.
    """
    # 1. Subject validation
    if subject_id is None:
        return {
            'success': False,
            'error_code': 'SUBJECT_REQUIRED',
            'action': 'SUBJECT_REQUIRED',
            'attendance_type': 'COMBINED',
            'message': 'Subject must be selected for combined attendance.'
        }

    try:
        subject_id = int(subject_id)
    except (ValueError, TypeError):
        return {
            'success': False,
            'error_code': 'INVALID_SUBJECT',
            'action': 'INVALID_SUBJECT',
            'attendance_type': 'COMBINED',
            'message': 'Invalid subject identifier provided.'
        }

    subject = Subject.query.get(subject_id)
    if not subject:
        return {
            'success': False,
            'error_code': 'SUBJECT_NOT_FOUND',
            'action': 'SUBJECT_NOT_FOUND',
            'attendance_type': 'COMBINED',
            'message': f"Subject with ID {subject_id} does not exist."
        }

    if not subject.is_active:
        return {
            'success': False,
            'error_code': 'SUBJECT_INACTIVE',
            'action': 'SUBJECT_INACTIVE',
            'attendance_type': 'COMBINED',
            'message': f"Subject '{subject.subject_name}' ({subject.subject_code}) is currently inactive."
        }

    # 2. Authorization validation
    if is_teacher:
        # Check Coordinator authorization for this student
        if not teacher_obj or not teacher_obj.is_coordinator_for_student(student):
            return {
                'success': False,
                'error_code': 'UNAUTHORIZED_COORDINATOR',
                'action': 'UNAUTHORIZED_COORDINATOR',
                'attendance_type': 'COMBINED',
                'message': f"Access Denied: You are not authorized to take General Attendance for {student.full_name} ({student.course or 'Course'}, {student.semester or 'Sem'}, Sec {student.section or 'N/A'}). Only their assigned Class Coordinator can take Combined Attendance."
            }

        # Check Subject assignment authorization
        if not teacher_obj or not teacher_obj.is_assigned_to_subject(subject_id, semester=semester):
            sem_str = f" in {semester}" if semester else ""
            return {
                'success': False,
                'error_code': 'UNAUTHORIZED_SUBJECT',
                'action': 'UNAUTHORIZED_SUBJECT',
                'attendance_type': 'COMBINED',
                'message': f"Access Denied: You are not authorized to take attendance for {subject.subject_name} ({subject.subject_code}){sem_str}."
            }

        # If semester not explicitly passed, try resolving from teacher's active assignment
        if not semester and teacher_obj:
            assignment = teacher_obj.subject_assignments.filter_by(subject_id=subject_id, is_active=True).first()
            if assignment and assignment.semester:
                semester = assignment.semester

    elif not is_admin:
        return {
            'success': False,
            'error_code': 'UNAUTHORIZED',
            'action': 'UNAUTHORIZED',
            'attendance_type': 'COMBINED',
            'message': 'Unauthorized: Only Class Coordinators and Administrators can take Combined Attendance.'
        }

    if not semester and subject:
        semester = subject.semester

    teacher_id = teacher_obj.id if teacher_obj else None
    today = kwargs.get('att_date') or get_current_ist_date()
    now_time = kwargs.get('att_time') or get_current_ist_time()
    cooldown = int(SystemSetting.get_setting('duplicate_scan_cooldown_seconds', '30'))

    # 3. Query existing records for today
    gen_record = Attendance.query.filter(
        Attendance.student_id == student.id,
        Attendance.date == today,
        (Attendance.attendance_type == 'GENERAL') |
        (Attendance.attendance_type.is_(None) & Attendance.subject_id.is_(None))
    ).first()

    sub_record = Attendance.query.filter(
        Attendance.student_id == student.id,
        Attendance.date == today,
        Attendance.subject_id == subject_id,
        (Attendance.attendance_type == 'SUBJECT') | (Attendance.subject_id.is_(None))
    ).first()

    # --- Part A: General Attendance State Machine ---
    gen_action = None
    gen_status = 'Present'
    gen_msg = ''
    if not gen_record:
        gen_record = Attendance(
            student_id=student.id,
            attendance_type='GENERAL',
            subject_id=None,
            teacher_id=teacher_id,
            semester=student.semester,
            section=student.section,
            date=today,
            time_in=now_time,
            time_out=None,
            status='Present',
            marked_by=marker_user.id if marker_user and hasattr(marker_user, 'id') else None,
            method='QR'
        )
        db.session.add(gen_record)
        gen_action = 'TIME_IN'
        gen_status = 'Present'
        gen_msg = f"General: Time In marked at {now_time.strftime('%I:%M %p')}"
    else:
        # General Attendance is daily attendance and has already been recorded today
        gen_action = 'ALREADY_COMPLETED'
        gen_status = 'Already Completed'
        in_str = gen_record.time_in.strftime('%I:%M %p') if gen_record.time_in else '-'
        out_str = f", Out: {gen_record.time_out.strftime('%I:%M %p')}" if gen_record.time_out else ''
        gen_msg = f"General Attendance: Already Completed today (In: {in_str}{out_str})"

    # --- Part B: Subject Attendance State Machine ---
    sub_action = None
    sub_status = 'Present'
    sub_msg = ''
    if not sub_record:
        sub_record = Attendance(
            student_id=student.id,
            attendance_type='SUBJECT',
            subject_id=subject_id,
            teacher_id=teacher_id,
            semester=semester or student.semester,
            section=student.section,
            date=today,
            time_in=now_time,
            time_out=None,
            status='Present',
            marked_by=marker_user.id if marker_user and hasattr(marker_user, 'id') else None,
            method='QR'
        )
        db.session.add(sub_record)
        sub_action = 'TIME_IN'
        sub_status = 'Present'
        sub_msg = f"{subject.subject_name}: Time In marked at {now_time.strftime('%I:%M %p')}"
    elif sub_record.time_out is None:
        time_in_dt = datetime.combine(today, sub_record.time_in) if sub_record.time_in else None
        now_dt = datetime.combine(today, now_time)
        elapsed_seconds = (now_dt - time_in_dt).total_seconds() if time_in_dt else 999
        if 0 <= elapsed_seconds < cooldown:
            sub_action = 'ALREADY_COMPLETED'
            sub_status = 'Already Completed'
            sub_msg = f"{subject.subject_name}: Already completed (scanned {int(elapsed_seconds)}s ago)"
        else:
            sub_record.time_out = now_time
            if teacher_id and not sub_record.teacher_id:
                sub_record.teacher_id = teacher_id
            if semester and not sub_record.semester:
                sub_record.semester = semester
            sub_record.updated_at = datetime.utcnow()
            sub_action = 'TIME_OUT'
            sub_status = 'Present'
            sub_msg = f"{subject.subject_name}: Time Out marked at {now_time.strftime('%I:%M %p')}"
    else:
        sub_action = 'ALREADY_COMPLETED'
        sub_status = 'Already Completed'
        in_str = sub_record.time_in.strftime('%I:%M %p') if sub_record.time_in else '-'
        out_str = sub_record.time_out.strftime('%I:%M %p') if sub_record.time_out else '-'
        sub_msg = f"{subject.subject_name}: Already completed today (In: {in_str}, Out: {out_str})"

    # 4. Atomic database commit
    try:
        db.session.commit()
    except IntegrityError as ie:
        db.session.rollback()
        current_app.logger.warning(f"Integrity warning in combined attendance: {ie}. Querying existing records...")
        gen_record = Attendance.query.filter(
            Attendance.student_id == student.id,
            Attendance.date == today,
            (Attendance.attendance_type == 'GENERAL') | (Attendance.attendance_type.is_(None) & Attendance.subject_id.is_(None))
        ).first()
        sub_record = Attendance.query.filter(
            Attendance.student_id == student.id,
            Attendance.date == today,
            Attendance.subject_id == subject_id
        ).first()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Unexpected database error saving Combined Attendance: {e}")
        return {
            'success': False,
            'error_code': 'SERVER_ERROR',
            'action': 'SERVER_ERROR',
            'attendance_type': 'COMBINED',
            'message': f"Failed to save combined attendance: {str(e)}"
        }

    # 5. Determine combined action & audit log
    if gen_action == 'TIME_IN' or sub_action == 'TIME_IN':
        overall_action = 'TIME_IN'
    elif gen_action == 'TIME_OUT' or sub_action == 'TIME_OUT':
        overall_action = 'TIME_OUT'
    elif gen_action == 'ALREADY_COMPLETED' and sub_action == 'ALREADY_COMPLETED':
        overall_action = 'ALREADY_COMPLETED'
    elif gen_action == 'COOLDOWN' and sub_action == 'COOLDOWN':
        overall_action = 'COOLDOWN'
    else:
        overall_action = 'COMBINED_SUCCESS'

    overall_message = f"{student.full_name}: {gen_msg} | {sub_msg}"

    AuditLog.log(
        'ATTENDANCE_COMBINED',
        f"Combined Attendance for {student.student_id} ({student.full_name}): General={gen_action}, {subject.subject_code}={sub_action} at {now_time.strftime('%I:%M %p')}",
        user_id=marker_user.id if marker_user and hasattr(marker_user, 'id') else None
    )

    current_app.logger.info(
        f"ATTENDANCE_COMBINED: Teacher={teacher_id} Subject={subject_id} ({subject.subject_name}) "
        f"Student={student.student_id} GeneralAction={gen_action} SubjectAction={sub_action}"
    )

    return {
        'success': True,
        'action': overall_action,
        'attendance_type': 'COMBINED',
        'message': overall_message,
        'student': student.to_dict(),
        'subject_id': subject.id,
        'subject': {
            'id': subject.id,
            'code': subject.subject_code,
            'name': subject.subject_name,
            'semester': semester or (subject.semester if subject else None),
            'status': sub_status,
            'action': sub_action,
            'message': sub_msg,
            'attendance': sub_record.to_dict() if sub_record else None
        },
        'teacher': {
            'id': teacher_obj.id,
            'name': teacher_obj.full_name
        } if teacher_obj else None,
        'general': {
            'status': gen_status,
            'action': gen_action,
            'message': gen_msg,
            'attendance': gen_record.to_dict() if gen_record else None
        },
        'attendance': (sub_record or gen_record).to_dict() if (sub_record or gen_record) else None
    }

