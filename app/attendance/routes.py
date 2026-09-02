import calendar
from datetime import datetime, date, time
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.attendance import attendance_bp
from app.extensions import db
from app.models.student import Student
from app.models.attendance import Attendance
from app.models.holiday import Holiday
from app.models.department import Department
from app.models.audit import AuditLog
from app.utils.decorators import role_required
from app.attendance.services import process_qr_attendance

@attendance_bp.route('/scanner')
@login_required
@role_required('admin', 'teacher')
def scanner():
    today = date.today()
    recent_scans = Attendance.query.filter_by(date=today).order_by(
        Attendance.updated_at.desc()
    ).limit(10).all()

    return render_template('attendance/scanner.html', recent_scans=recent_scans, today=today)

@attendance_bp.route('/manual', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'teacher')
def manual():
    if request.method == 'POST':
        student_id_str = request.form.get('student_id', '').strip()
        att_date_str = request.form.get('date', '').strip()
        status = request.form.get('status', 'Present').strip()
        time_in_str = request.form.get('time_in', '').strip()
        time_out_str = request.form.get('time_out', '').strip()
        remarks = request.form.get('remarks', '').strip()

        student = Student.query.filter(
            (Student.student_id == student_id_str) | (Student.id == student_id_str)
        ).first()

        if not student:
            flash(f"Student '{student_id_str}' not found.", 'danger')
            return redirect(url_for('attendance.manual'))

        try:
            att_date = datetime.strptime(att_date_str, '%Y-%m-%d').date() if att_date_str else date.today()
        except ValueError:
            att_date = date.today()

        time_in = None
        if time_in_str:
            try:
                time_in = datetime.strptime(time_in_str, '%H:%M').time()
            except ValueError:
                time_in = datetime.now().time()

        time_out = None
        if time_out_str:
            try:
                time_out = datetime.strptime(time_out_str, '%H:%M').time()
            except ValueError:
                pass

        # Check existing record for that student + date
        record = Attendance.query.filter_by(student_id=student.id, date=att_date).first()
        method_name = 'Admin' if current_user.is_admin else 'Manual'

        if record:
            record.status = status
            record.time_in = time_in
            record.time_out = time_out
            record.remarks = remarks
            record.marked_by = current_user.id
            record.method = method_name
            record.updated_at = datetime.utcnow()
            AuditLog.log('ATTENDANCE_MANUAL_UPDATE', f"Manual update for {student.student_id} on {att_date} to {status}", user_id=current_user.id)
            flash(f"Attendance for {student.full_name} updated successfully.", 'success')
        else:
            record = Attendance(
                student_id=student.id,
                date=att_date,
                time_in=time_in or datetime.now().time(),
                time_out=time_out,
                status=status,
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
        today=today,
        recent_manual=recent_manual
    )

@attendance_bp.route('/calendar', endpoint='calendar')
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
        return redirect(url_for('attendance.calendar_view'))

    try:
        hdate = datetime.strptime(hdate_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format.', 'danger')
        return redirect(url_for('attendance.calendar_view'))

    existing = Holiday.query.filter_by(date=hdate).first()
    if existing:
        flash(f"A holiday '{existing.title}' already exists on {hdate}.", 'warning')
        return redirect(url_for('attendance.calendar_view'))

    holiday = Holiday(title=title, date=hdate, description=desc)
    db.session.add(holiday)
    db.session.commit()
    AuditLog.log('HOLIDAY_ADD', f"Added holiday {title} on {hdate}", user_id=current_user.id)
    flash(f"Holiday '{title}' added.", 'success')
    return redirect(url_for('attendance.calendar_view', year=hdate.year, month=hdate.month))

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
    return redirect(url_for('attendance.calendar_view'))
