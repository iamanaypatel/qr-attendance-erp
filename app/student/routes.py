from datetime import datetime, date
from flask import render_template, redirect, url_for, flash, request, send_file, current_app
from flask_login import login_required, current_user
from app.student import student_bp
from app.extensions import db
from app.models.attendance import Attendance
from app.models.settings import SystemSetting
from app.utils.decorators import role_required
from app.utils.qr_generator import generate_qr_data_uri, generate_qr_bytes
from app.utils.id_card import generate_student_id_card_pdf

@student_bp.route('/dashboard')
@login_required
@role_required('student', 'admin')
def dashboard():
    student = current_user.student_profile
    if not student:
        flash('Student record not associated with this account.', 'warning')
        return render_template('student/no_profile.html')

    stats = student.calculate_attendance_stats()
    recent_records = student.attendances.order_by(Attendance.date.desc()).limit(10).all()

    return render_template(
        'student/dashboard.html',
        student=student,
        stats=stats,
        recent_records=recent_records
    )

@student_bp.route('/profile')
@login_required
@role_required('student', 'admin')
def profile():
    student = current_user.student_profile
    if not student:
        flash('No student profile found.', 'warning')
        return redirect(url_for('student.dashboard'))

    stats = student.calculate_attendance_stats()
    qr_uri = generate_qr_data_uri(student.qr_token, box_size=8)

    return render_template('student/profile.html', student=student, stats=stats, qr_uri=qr_uri)

@student_bp.route('/qr-code')
@login_required
@role_required('student', 'admin')
def qr_code():
    student = current_user.student_profile
    if not student:
        flash('No student profile found.', 'warning')
        return redirect(url_for('student.dashboard'))

    qr_uri = generate_qr_data_uri(student.qr_token, box_size=10, border=2)
    return render_template('student/qr_code.html', student=student, qr_uri=qr_uri)

@student_bp.route('/qr-code/download')
@login_required
@role_required('student', 'admin')
def qr_download():
    student = current_user.student_profile
    if not student:
        flash('No student profile found.', 'warning')
        return redirect(url_for('student.dashboard'))

    buf = generate_qr_bytes(student.qr_token, box_size=12, border=2)
    return send_file(
        buf,
        mimetype='image/png',
        as_attachment=True,
        download_name=f"My_QR_{student.student_id}.png"
    )

@student_bp.route('/history')
@login_required
@role_required('student', 'admin')
def history():
    student = current_user.student_profile
    if not student:
        flash('No student profile found.', 'warning')
        return redirect(url_for('student.dashboard'))

    page = request.args.get('page', 1, type=int)
    month = request.args.get('month', type=int)
    status_filter = request.args.get('status', '').strip()

    query = student.attendances
    if status_filter:
        query = query.filter(Attendance.status == status_filter)

    pagination = query.order_by(Attendance.date.desc()).paginate(page=page, per_page=15, error_out=False)
    stats = student.calculate_attendance_stats()

    return render_template(
        'student/history.html',
        student=student,
        pagination=pagination,
        records=pagination.items,
        stats=stats,
        selected_status=status_filter
    )

@student_bp.route('/id-card')
@login_required
@role_required('student', 'admin')
def id_card():
    student = current_user.student_profile
    if not student:
        flash('No student profile found.', 'warning')
        return redirect(url_for('student.dashboard'))

    qr_uri = generate_qr_data_uri(student.qr_token, box_size=6, border=1)
    return render_template('student/id_card.html', student=student, qr_uri=qr_uri)

@student_bp.route('/id-card/download')
@login_required
@role_required('student', 'admin')
def id_card_download():
    student = current_user.student_profile
    if not student:
        flash('No student profile found.', 'warning')
        return redirect(url_for('student.dashboard'))

    inst_name = SystemSetting.get_setting('institution_name', current_app.config['INSTITUTION_NAME'])
    pdf_buffer = generate_student_id_card_pdf(student, institution_name=inst_name)
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"ID_Card_{student.student_id}.pdf"
    )
