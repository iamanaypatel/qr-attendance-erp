from datetime import datetime, date, time
from flask import current_app
from app.extensions import db
from app.models.student import Student
from app.models.attendance import Attendance
from app.models.settings import SystemSetting
from app.models.audit import AuditLog

def process_qr_attendance(token: str, marker_user) -> dict:
    """
    Core business logic for QR code attendance verification and state machine:
    1. Validate token -> Student
    2. Check today's attendance record
    3. First scan of the day -> Record Time In
    4. Second scan of the day -> Record Time Out
    5. Subsequent scan -> Informative duplicate warning with timestamps
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

    today = date.today()
    now_time = datetime.now().time()

    # Look up existing record for today
    record = Attendance.query.filter_by(student_id=student.id, date=today).first()

    if not record:
        # Case 1: First scan of the day -> Check In (Time In)
        record = Attendance(
            student_id=student.id,
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
            f"Time In for {student.student_id} at {now_time.strftime('%I:%M %p')}",
            user_id=marker_user.id if marker_user and hasattr(marker_user, 'id') else None
        )

        return {
            'success': True,
            'action': 'TIME_IN',
            'message': f"Time In marked successfully for {student.full_name} at {now_time.strftime('%I:%M %p')}.",
            'student': student.to_dict(),
            'attendance': {
                'date': today.strftime('%Y-%m-%d'),
                'time_in': now_time.strftime('%I:%M %p'),
                'time_out': None,
                'status': 'Present',
                'method': 'QR'
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
                    'student': student.to_dict()
                }

        record.time_out = now_time
        record.updated_at = datetime.utcnow()
        db.session.commit()

        AuditLog.log(
            'ATTENDANCE_TIME_OUT',
            f"Time Out for {student.student_id} at {now_time.strftime('%I:%M %p')}",
            user_id=marker_user.id if marker_user and hasattr(marker_user, 'id') else None
        )

        return {
            'success': True,
            'action': 'TIME_OUT',
            'message': f"Time Out marked successfully for {student.full_name} at {now_time.strftime('%I:%M %p')}.",
            'student': student.to_dict(),
            'attendance': {
                'date': today.strftime('%Y-%m-%d'),
                'time_in': record.time_in.strftime('%I:%M %p') if record.time_in else '-',
                'time_out': now_time.strftime('%I:%M %p'),
                'status': record.status,
                'method': record.method
            }
        }

    # Case 3: Both Time In and Time Out already completed for today
    return {
        'success': False,
        'action': 'ALREADY_COMPLETED',
        'message': f"Attendance already completed for {student.full_name} today (In: {record.time_in.strftime('%I:%M %p')}, Out: {record.time_out.strftime('%I:%M %p')}).",
        'student': student.to_dict(),
        'attendance': {
            'date': today.strftime('%Y-%m-%d'),
            'time_in': record.time_in.strftime('%I:%M %p') if record.time_in else '-',
            'time_out': record.time_out.strftime('%I:%M %p') if record.time_out else '-',
            'status': record.status
        }
    }
