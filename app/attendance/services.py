from datetime import datetime, date, time
from flask import current_app
from app.extensions import db
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.subject import Subject
from app.models.attendance import Attendance
from app.models.settings import SystemSetting
from app.models.audit import AuditLog

def process_qr_attendance(token: str, marker_user, subject_id: int = None) -> dict:
    """
    Core business logic for QR code attendance verification and state machine:
    1. Validate token -> Student
    2. Validate subject and verify teacher authorization if subject_id is provided
    3. Check today's attendance record for this specific student + subject
    4. First scan -> Record Time In (linked with subject_id and teacher_id)
    5. Second scan -> Record Time Out
    6. Subsequent scan -> Informative duplicate warning with timestamps
    """
    if not token or not token.strip():
        return {
            'success': False,
            'message': 'Invalid scan: No QR token provided.'
        }

    token = token.strip()
    student = Student.query.filter_by(qr_token=token).first()
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

    # Subject & Teacher Authorization Validation
    subject = None
    teacher_obj = None

    if subject_id is not None:
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

    # Identify if marker_user is a teacher
    is_teacher = getattr(marker_user, 'is_teacher', False) or getattr(marker_user, 'role', '') == 'teacher'
    is_admin = getattr(marker_user, 'is_admin', False) or getattr(marker_user, 'role', '') == 'admin'

    if is_teacher:
        teacher_obj = getattr(marker_user, 'teacher_profile', None)
        if not teacher_obj and hasattr(marker_user, 'id'):
            teacher_obj = Teacher.query.filter_by(user_id=marker_user.id).first()

        # If subject is specified, verify teacher assignment
        if subject_id is not None:
            if not teacher_obj or not teacher_obj.is_assigned_to_subject(subject_id):
                return {
                    'success': False,
                    'message': f"Access Denied: You are not authorized to take attendance for {subject.subject_name} ({subject.subject_code})."
                }
    elif is_admin:
        # Admin can take attendance for any subject; resolve teacher profile if admin happens to be linked to one
        teacher_obj = getattr(marker_user, 'teacher_profile', None)

    teacher_id = teacher_obj.id if teacher_obj else None

    today = date.today()
    now_time = datetime.now().time()

    # Look up existing record for today scoped to (student_id, date, subject_id)
    query = Attendance.query.filter(Attendance.student_id == student.id, Attendance.date == today)
    if subject_id is not None:
        query = query.filter(Attendance.subject_id == subject_id)
    else:
        query = query.filter(Attendance.subject_id.is_(None))

    record = query.first()
    subject_label = f" in {subject.subject_name}" if subject else ""

    if not record:
        # Case 1: First scan -> Check In (Time In)
        record = Attendance(
            student_id=student.id,
            subject_id=subject_id,
            teacher_id=teacher_id,
            date=today,
            time_in=now_time,
            time_out=None,
            status='Present',
            marked_by=marker_user.id if marker_user and hasattr(marker_user, 'id') else None,
            method='QR'
        )
        db.session.add(record)
        db.session.commit()

        AuditLog.log(
            'ATTENDANCE_TIME_IN',
            f"Time In for {student.student_id}{subject_label} at {now_time.strftime('%I:%M %p')}",
            user_id=marker_user.id if marker_user and hasattr(marker_user, 'id') else None
        )

        return {
            'success': True,
            'action': 'TIME_IN',
            'message': f"Time In marked successfully for {student.full_name}{subject_label} at {now_time.strftime('%I:%M %p')}.",
            'student': student.to_dict(),
            'subject': {
                'id': subject.id,
                'code': subject.subject_code,
                'name': subject.subject_name
            } if subject else None,
            'teacher': {
                'id': teacher_obj.id,
                'name': teacher_obj.full_name
            } if teacher_obj else None,
            'attendance': {
                'date': today.strftime('%Y-%m-%d'),
                'time_in': now_time.strftime('%I:%M %p'),
                'time_out': None,
                'status': 'Present',
                'method': 'QR',
                'subject_name': subject.subject_name if subject else None
            }
        }

    # Case 2: Record exists, but Time Out has not been marked yet
    if record.time_out is None:
        # Check cooldown to prevent accidental double-tap within seconds
        cooldown = int(SystemSetting.get_setting('duplicate_scan_cooldown_seconds', '30'))
        if record.time_in:
            time_in_dt = datetime.combine(today, record.time_in)
            now_dt = datetime.combine(today, now_time)
            elapsed_seconds = (now_dt - time_in_dt).total_seconds()
            if elapsed_seconds < cooldown:
                return {
                    'success': False,
                    'action': 'COOLDOWN',
                    'message': f"Scan cooldown active: Time In was just recorded {int(elapsed_seconds)}s ago. Please wait.",
                    'student': student.to_dict(),
                    'subject': {
                        'id': subject.id,
                        'code': subject.subject_code,
                        'name': subject.subject_name
                    } if subject else None
                }

        record.time_out = now_time
        if teacher_id and not record.teacher_id:
            record.teacher_id = teacher_id
        record.updated_at = datetime.utcnow()
        db.session.commit()

        AuditLog.log(
            'ATTENDANCE_TIME_OUT',
            f"Time Out for {student.student_id}{subject_label} at {now_time.strftime('%I:%M %p')}",
            user_id=marker_user.id if marker_user and hasattr(marker_user, 'id') else None
        )

        return {
            'success': True,
            'action': 'TIME_OUT',
            'message': f"Time Out marked successfully for {student.full_name}{subject_label} at {now_time.strftime('%I:%M %p')}.",
            'student': student.to_dict(),
            'subject': {
                'id': subject.id,
                'code': subject.subject_code,
                'name': subject.subject_name
            } if subject else None,
            'teacher': {
                'id': teacher_obj.id,
                'name': teacher_obj.full_name
            } if teacher_obj else None,
            'attendance': {
                'date': today.strftime('%Y-%m-%d'),
                'time_in': record.time_in.strftime('%I:%M %p') if record.time_in else '-',
                'time_out': now_time.strftime('%I:%M %p'),
                'status': record.status,
                'method': record.method,
                'subject_name': subject.subject_name if subject else None
            }
        }

    # Case 3: Both Time In and Time Out already completed for today in this subject session
    return {
        'success': False,
        'action': 'ALREADY_COMPLETED',
        'message': f"Attendance already completed for {student.full_name}{subject_label} today (In: {record.time_in.strftime('%I:%M %p')}, Out: {record.time_out.strftime('%I:%M %p')}).",
        'student': student.to_dict(),
        'subject': {
            'id': subject.id,
            'code': subject.subject_code,
            'name': subject.subject_name
        } if subject else None,
        'attendance': {
            'date': today.strftime('%Y-%m-%d'),
            'time_in': record.time_in.strftime('%I:%M %p') if record.time_in else '-',
            'time_out': record.time_out.strftime('%I:%M %p') if record.time_out else '-',
            'status': record.status,
            'subject_name': subject.subject_name if subject else None
        }
    }
