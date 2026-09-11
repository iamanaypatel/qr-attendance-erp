import calendar
from datetime import datetime, date, time
from flask import render_template, request, jsonify, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.attendance import attendance_bp
from app.extensions import db
from app.models.student import Student
from app.models.attendance import Attendance
from app.models.holiday import Holiday
from app.models.department import Department
from app.models.audit import AuditLog
from app.utils.decorators import role_required
from app.utils.timezone import get_current_ist_date, get_current_ist_time
from app.attendance.services import process_qr_attendance

@attendance_bp.route('/scanner')
@login_required
@role_required('admin', 'teacher')
def scanner():
    today = get_current_ist_date()
    attendance_type = request.args.get('type', '').strip().upper()
    selected_subject_id = request.args.get('subject_id', type=int)
    selected_semester = request.args.get('semester', '').strip()
    selected_assignment_id = request.args.get('assignment_id', type=int)

    from app.models.subject import Subject
    from app.models.subject_assignment import TeacherSubjectAssignment
    from app.models.class_coordinator import ClassCoordinator

    coordinator_assignments = []
    if current_user.is_teacher and current_user.teacher_profile:
        coordinator_assignments = current_user.teacher_profile.get_active_coordinator_assignments()
    elif current_user.is_admin:
        coordinator_assignments = ClassCoordinator.query.filter_by(is_active=True).all()

    assignments_data = []
    selected_assignment = None

    if current_user.is_teacher and current_user.teacher_profile:
        assignments = current_user.teacher_profile.get_active_assignments()
        assignment_count = len(assignments)

        for asgn in assignments:
            s = asgn.subject
            if not s or not s.is_active:
                continue
            item = {
                'id': asgn.id,
                'subject_id': s.id,
                'subject_name': s.subject_name,
                'subject_code': s.subject_code,
                'teacher_name': asgn.teacher.full_name if asgn.teacher else current_user.teacher_profile.full_name,
                'semester': asgn.semester or (s.semester or ''),
                'department': asgn.department.name if asgn.department else (s.department.name if s.department else 'General'),
                'course': asgn.course or (s.course or 'General'),
                'section': asgn.section or ''
            }
            assignments_data.append(item)

        if assignment_count == 1:
            selected_assignment = assignments_data[0]
            selected_subject_id = selected_assignment['subject_id']
            selected_semester = selected_assignment['semester']
        elif assignment_count > 1:
            if selected_assignment_id:
                found = next((a for a in assignments_data if a['id'] == selected_assignment_id), None)
                if found:
                    selected_assignment = found
            if not selected_assignment and selected_subject_id:
                found = next((a for a in assignments_data if a['subject_id'] == selected_subject_id and (not selected_semester or a['semester'] == selected_semester)), None)
                if found:
                    selected_assignment = found
            if not selected_assignment and assignments_data:
                selected_assignment = assignments_data[0]

            if selected_assignment:
                selected_subject_id = selected_assignment['subject_id']
                selected_semester = selected_assignment['semester']
    else:
        # Admin view
        assignments = TeacherSubjectAssignment.query.filter_by(is_active=True).all()
        assignment_count = len(assignments)
        if assignments:
            for asgn in assignments:
                s = asgn.subject
                if not s or not s.is_active:
                    continue
                assignments_data.append({
                    'id': asgn.id,
                    'subject_id': s.id,
                    'subject_name': s.subject_name,
                    'subject_code': s.subject_code,
                    'teacher_name': asgn.teacher.full_name if asgn.teacher else 'Admin',
                    'semester': asgn.semester or (s.semester or ''),
                    'department': asgn.department.name if asgn.department else (s.department.name if s.department else 'General'),
                    'course': asgn.course or (s.course or 'General'),
                    'section': asgn.section or ''
                })
        else:
            subjects = Subject.query.filter_by(is_active=True).order_by(Subject.subject_code).all()
            for s in subjects:
                assignments_data.append({
                    'id': s.id,
                    'subject_id': s.id,
                    'subject_name': s.subject_name,
                    'subject_code': s.subject_code,
                    'teacher_name': 'Administrator',
                    'semester': s.semester or '',
                    'department': s.department.name if s.department else 'General',
                    'course': s.course or 'General',
                    'section': ''
                })
        if assignments_data:
            selected_assignment = assignments_data[0]
            selected_subject_id = selected_assignment['subject_id']
            selected_semester = selected_assignment['semester']

    # Auto-resolve attendance_type if not explicitly passed
    if not attendance_type:
        if not assignments_data and coordinator_assignments:
            attendance_type = 'GENERAL'
        else:
            attendance_type = 'SUBJECT'

    selected_coordinator = coordinator_assignments[0] if coordinator_assignments else None

    recent_query = Attendance.query.filter_by(date=today)
    if attendance_type == 'GENERAL':
        recent_query = recent_query.filter(
            (Attendance.attendance_type == 'GENERAL') | (Attendance.subject_id.is_(None))
        )
        if current_user.is_teacher and current_user.teacher_profile:
            recent_query = recent_query.filter_by(teacher_id=current_user.teacher_profile.id)
    else:
        if selected_subject_id:
            recent_query = recent_query.filter_by(subject_id=selected_subject_id)
            if selected_semester:
                recent_query = recent_query.filter(Attendance.semester.ilike(selected_semester))
    recent_scans = recent_query.order_by(Attendance.updated_at.desc()).limit(10).all()

    return render_template(
        'attendance/scanner.html',
        recent_scans=recent_scans,
        today=today,
        attendance_type=attendance_type,
        coordinator_assignments=coordinator_assignments,
        selected_coordinator=selected_coordinator,
        assignments=assignments_data,
        assignment_count=len(assignments_data) if (current_user.is_teacher and current_user.teacher_profile) else len(assignments_data),
        selected_assignment=selected_assignment,
        selected_subject_id=selected_subject_id,
        selected_semester=selected_semester
    )

@attendance_bp.route('/manual', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'teacher')
def manual():
    from app.models.subject import Subject

    if current_user.is_teacher and current_user.teacher_profile:
        available_subjects = current_user.teacher_profile.assigned_subjects.filter_by(is_active=True).order_by(Subject.subject_name).all()
    else:
        available_subjects = Subject.query.filter_by(is_active=True).order_by(Subject.subject_name).all()

    if request.method == 'POST':
        student_id_str = request.form.get('student_id', '').strip()
        att_date_str = request.form.get('date', '').strip()
        status = request.form.get('status', 'Present').strip()
        time_in_str = request.form.get('time_in', '').strip()
        time_out_str = request.form.get('time_out', '').strip()
        remarks = request.form.get('remarks', '').strip()
        subject_id_str = request.form.get('subject_id', '').strip()
        semester = request.form.get('semester', '').strip()

        subject_id = None
        if subject_id_str:
            try:
                subject_id = int(subject_id_str)
            except (ValueError, TypeError):
                subject_id = None

        # Verify teacher authorization for subject (and semester if provided)
        if subject_id and current_user.is_teacher:
            if not current_user.teacher_profile or not current_user.teacher_profile.is_assigned_to_subject(subject_id, semester=semester if semester else None):
                flash("Unauthorized: You are not assigned to take attendance for this subject.", "danger")
                return redirect(url_for('attendance.manual'))

        if subject_id and not semester:
            if current_user.is_teacher and current_user.teacher_profile:
                asgn = current_user.teacher_profile.subject_assignments.filter_by(subject_id=subject_id, is_active=True).first()
                if asgn and asgn.semester:
                    semester = asgn.semester
            if not semester:
                sub_obj = Subject.query.get(subject_id)
                if sub_obj and sub_obj.semester:
                    semester = sub_obj.semester

        student = Student.query.filter(
            (Student.student_id == student_id_str) | (Student.id == student_id_str)
        ).first()

        if not student:
            flash(f"Student '{student_id_str}' not found.", 'danger')
            return redirect(url_for('attendance.manual'))

        try:
            att_date = datetime.strptime(att_date_str, '%Y-%m-%d').date() if att_date_str else get_current_ist_date()
        except ValueError:
            att_date = get_current_ist_date()

        time_in = None
        if time_in_str:
            try:
                time_in = datetime.strptime(time_in_str, '%H:%M').time()
            except ValueError:
                time_in = get_current_ist_time()

        time_out = None
        if time_out_str:
            try:
                time_out = datetime.strptime(time_out_str, '%H:%M').time()
            except ValueError:
                pass

        attendance_type = request.form.get('attendance_type', '').strip().upper()
        if not attendance_type:
            attendance_type = 'SUBJECT' if subject_id else 'GENERAL'

        # Check existing record for that student + date + context
        query = Attendance.query.filter(Attendance.student_id == student.id, Attendance.date == att_date)
        if attendance_type == 'GENERAL' or not subject_id:
            query = query.filter((Attendance.attendance_type == 'GENERAL') | (Attendance.subject_id.is_(None)))
        else:
            query = query.filter(Attendance.subject_id == subject_id)
            if semester:
                query = query.filter(Attendance.semester == semester)
        record = query.first()

        method_name = 'Admin' if current_user.is_admin else 'Manual'
        teacher_id = current_user.teacher_profile.id if current_user.is_teacher and current_user.teacher_profile else None

        if record:
            record.status = status
            record.attendance_type = attendance_type
            record.time_in = time_in
            record.time_out = time_out
            record.remarks = remarks
            record.marked_by = current_user.id
            if semester:
                record.semester = semester
            if teacher_id:
                record.teacher_id = teacher_id
            record.method = method_name
            record.updated_at = datetime.utcnow()
            AuditLog.log('ATTENDANCE_MANUAL_UPDATE', f"Manual update for {student.student_id} on {att_date} to {status}", user_id=current_user.id)
            flash(f"Attendance for {student.full_name} updated successfully.", 'success')
        else:
            record = Attendance(
                student_id=student.id,
                subject_id=subject_id if attendance_type == 'SUBJECT' else None,
                teacher_id=teacher_id,
                semester=semester,
                date=att_date,
                time_in=time_in or datetime.now().time(),
                time_out=time_out,
                status=status,
                attendance_type=attendance_type,
                remarks=remarks,
                marked_by=current_user.id,
                method=method_name
            )
            db.session.add(record)
            AuditLog.log('ATTENDANCE_MANUAL_CREATE', f"Manual record created for {student.student_id} on {att_date} as {status}", user_id=current_user.id)
            flash(f"Attendance for {student.full_name} marked as {status}.", 'success')

        db.session.commit()
        return redirect(url_for('attendance.manual'))

    today = date.today()
    students = Student.query.filter_by(is_active=True).order_by(Student.full_name).all()
    departments = Department.query.order_by(Department.name).all()

    # Recent manual logs
    recent_manual = Attendance.query.filter(
        Attendance.method.in_(['Manual', 'Admin'])
    ).order_by(Attendance.updated_at.desc()).limit(15).all()

    return render_template(
        'attendance/manual.html',
        students=students,
        departments=departments,
        available_subjects=available_subjects,
        today=today,
        recent_manual=recent_manual
    )

@attendance_bp.route('/calendar', endpoint='calendar')
@attendance_bp.route('/calendar', endpoint='calendar_view')
@login_required
def calendar_view():
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)

    # Validate month
    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1

    cal = calendar.Calendar(firstweekday=calendar.SUNDAY)
    month_days = cal.monthdatescalendar(year, month)

    # Query holidays in this month range
    first_date = month_days[0][0]
    last_date = month_days[-1][-1]
    holidays = Holiday.query.filter(Holiday.date >= first_date, Holiday.date <= last_date).all()
    holiday_map = {h.date: h.title for h in holidays}

    # Query attendance records for current user if student
    user_attendance = {}
    if current_user.is_student and current_user.student_profile:
        recs = Attendance.query.filter(
            Attendance.student_id == current_user.student_profile.id,
            Attendance.date >= first_date,
            Attendance.date <= last_date
        ).all()
        for r in recs:
            user_attendance[r.date] = r.status
    elif current_user.is_admin or current_user.is_teacher:
        # For admin/teacher, show daily present count
        recs = Attendance.query.filter(
            Attendance.date >= first_date,
            Attendance.date <= last_date,
            Attendance.status.in_(['Present', 'Late', 'Half Day'])
        ).all()
        for r in recs:
            user_attendance[r.date] = user_attendance.get(r.date, 0) + 1

    month_name = calendar.month_name[month]

    # Prev and Next month navigation parameters
    prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
    next_year, next_month = (year, month + 1) if month < 12 else (year + 1, 1)

    all_holidays = Holiday.query.order_by(Holiday.date.asc()).all()

    return render_template(
        'attendance/calendar.html',
        year=year,
        month=month,
        month_name=month_name,
        month_days=month_days,
        holiday_map=holiday_map,
        user_attendance=user_attendance,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
        all_holidays=all_holidays,
        today=date.today()
    )

@attendance_bp.route('/calendar/holiday/add', methods=['POST'])
@login_required
@role_required('admin')
def add_holiday():
    title = request.form.get('title', '').strip()
    hdate_str = request.form.get('date', '').strip()
    desc = request.form.get('description', '').strip()

    if not title or not hdate_str:
        flash('Holiday title and date are required.', 'danger')
        return redirect(url_for('attendance.calendar'))

    try:
        hdate = datetime.strptime(hdate_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format.', 'danger')
        return redirect(url_for('attendance.calendar'))

    existing = Holiday.query.filter_by(date=hdate).first()
    if existing:
        flash(f"A holiday '{existing.title}' already exists on {hdate}.", 'warning')
        return redirect(url_for('attendance.calendar'))

    holiday = Holiday(title=title, date=hdate, description=desc)
    db.session.add(holiday)
    db.session.commit()
    AuditLog.log('HOLIDAY_ADD', f"Added holiday {title} on {hdate}", user_id=current_user.id)
    flash(f"Holiday '{title}' added.", 'success')
    return redirect(url_for('attendance.calendar', year=hdate.year, month=hdate.month))

@attendance_bp.route('/calendar/holiday/<int:id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def delete_holiday(id):
    holiday = Holiday.query.get_or_404(id)
    title = holiday.title
    db.session.delete(holiday)
    db.session.commit()
    AuditLog.log('HOLIDAY_DELETE', f"Deleted holiday {title}", user_id=current_user.id)
    flash(f"Holiday '{title}' deleted.", 'info')
    return redirect(url_for('attendance.calendar'))
