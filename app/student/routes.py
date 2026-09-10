from datetime import datetime, date
from flask import render_template, redirect, url_for, flash, request, send_file, current_app, abort
from flask_login import login_required, current_user
from app.student import student_bp
from app.extensions import db
from app.models.student import Student
from app.models.attendance import Attendance
from app.models.settings import SystemSetting
from app.utils.decorators import role_required
from app.utils.qr_generator import generate_qr_data_uri, generate_qr_bytes
from app.utils.id_card import generate_student_id_card_pdf
from app.utils.photo import validate_and_save_photo

def _verify_student_query_param(student):
    """Reject requests where a student attempts to query or manipulate another student's ID."""
    if current_user.is_student and student:
        for param in ('student_id', 'card_id', 'id', 'selected_student_id'):
            val = request.args.get(param)
            if val and str(val).strip() not in (student.student_id, str(student.id)):
                abort(403)

@student_bp.route('/dashboard')
@login_required
@role_required('student', 'admin')
def dashboard():
    student = current_user.student
    if not student:
        flash('Student profile is not linked to this account. Please contact the administrator.', 'warning')
        return render_template('student/no_profile.html')

    _verify_student_query_param(student)

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
    student = current_user.student
    if not student:
        flash('Student profile is not linked to this account. Please contact the administrator.', 'warning')
        return redirect(url_for('student.dashboard'))

    _verify_student_query_param(student)

    stats = student.calculate_attendance_stats()
    qr_uri = generate_qr_data_uri(student.qr_token, box_size=8)

    return render_template('student/profile.html', student=student, stats=stats, qr_uri=qr_uri)

@student_bp.route('/profile/<student_identifier>')
@login_required
@role_required('student', 'admin')
def profile_with_id(student_identifier):
    student = current_user.student
    if not student:
        flash('Student profile is not linked to this account. Please contact the administrator.', 'warning')
        return redirect(url_for('student.dashboard'))

    if current_user.is_student:
        if str(student_identifier).strip() not in (student.student_id, str(student.id)):
            abort(403)
        return redirect(url_for('student.profile'))

    target = Student.query.filter(
        (Student.student_id == student_identifier) | (Student.id == student_identifier)
    ).first_or_404()
    stats = target.calculate_attendance_stats()
    qr_uri = generate_qr_data_uri(target.qr_token, box_size=8)
    return render_template('student/profile.html', student=target, stats=stats, qr_uri=qr_uri)

@student_bp.route('/profile/photo', methods=['POST'])
@login_required
@role_required('student', 'admin')
def upload_photo():
    student = current_user.student
    if not student:
        flash('Student profile is not linked to this account. Please contact the administrator.', 'warning')
        return redirect(url_for('student.dashboard'))

    _verify_student_query_param(student)

    photo_file = request.files.get('photo')
    if not photo_file or not photo_file.filename:
        flash('Please select an image file to upload.', 'warning')
        return redirect(url_for('student.profile'))

    saved_filename, error_msg = validate_and_save_photo(
        photo_file,
        student_id=student.student_id,
        old_photo_filename=student.photo
    )

    if error_msg:
        flash(error_msg, 'danger')
        return redirect(url_for('student.profile'))

    student.photo = saved_filename
    student.updated_at = datetime.utcnow()
    db.session.commit()

    flash('Profile photo updated successfully!', 'success')
    return redirect(url_for('student.profile'))


@student_bp.route('/qr-code')
@login_required
@role_required('student', 'admin')
def qr_code():
    student = current_user.student
    if not student:
        flash('Student profile is not linked to this account. Please contact the administrator.', 'warning')
        return redirect(url_for('student.dashboard'))

    _verify_student_query_param(student)

    qr_uri = generate_qr_data_uri(student.qr_token, box_size=10, border=2)
    return render_template('student/qr_code.html', student=student, qr_uri=qr_uri)

@student_bp.route('/qr-code/<student_identifier>')
@login_required
@role_required('student', 'admin')
def qr_code_with_id(student_identifier):
    student = current_user.student
    if not student:
        flash('Student profile is not linked to this account. Please contact the administrator.', 'warning')
        return redirect(url_for('student.dashboard'))

    if current_user.is_student:
        if str(student_identifier).strip() not in (student.student_id, str(student.id)):
            abort(403)
        return redirect(url_for('student.qr_code'))

    target = Student.query.filter(
        (Student.student_id == student_identifier) | (Student.id == student_identifier)
    ).first_or_404()
    qr_uri = generate_qr_data_uri(target.qr_token, box_size=10, border=2)
    return render_template('student/qr_code.html', student=target, qr_uri=qr_uri)

@student_bp.route('/qr-code/download')
@login_required
@role_required('student', 'admin')
def qr_download():
    student = current_user.student
    if not student:
        flash('Student profile is not linked to this account. Please contact the administrator.', 'warning')
        return redirect(url_for('student.dashboard'))

    _verify_student_query_param(student)

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
    student = current_user.student
    if not student:
        flash('Student profile is not linked to this account. Please contact the administrator.', 'warning')
        return redirect(url_for('student.dashboard'))

    _verify_student_query_param(student)

    page = request.args.get('page', 1, type=int)
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
    student = current_user.student
    if not student:
        flash('Student profile is not linked to this account. Please contact the administrator.', 'warning')
        return redirect(url_for('student.dashboard'))

    _verify_student_query_param(student)

    qr_uri = generate_qr_data_uri(student.qr_token, box_size=6, border=1)
    return render_template('student/id_card.html', student=student, qr_uri=qr_uri)

@student_bp.route('/id-card/<student_identifier>')
@login_required
@role_required('student', 'admin')
def id_card_with_id(student_identifier):
    student = current_user.student
    if not student:
        flash('Student profile is not linked to this account. Please contact the administrator.', 'warning')
        return redirect(url_for('student.dashboard'))

    if current_user.is_student:
        if str(student_identifier).strip() not in (student.student_id, str(student.id)):
            abort(403)
        return redirect(url_for('student.id_card'))

    target = Student.query.filter(
        (Student.student_id == student_identifier) | (Student.id == student_identifier)
    ).first_or_404()
    qr_uri = generate_qr_data_uri(target.qr_token, box_size=6, border=1)
    return render_template('student/id_card.html', student=target, qr_uri=qr_uri)

@student_bp.route('/id-card/download')
@login_required
@role_required('student', 'admin')
def id_card_download():
    student = current_user.student
    if not student:
        flash('Student profile is not linked to this account. Please contact the administrator.', 'warning')
        return redirect(url_for('student.dashboard'))

    _verify_student_query_param(student)

    inst_name = SystemSetting.get_setting('institution_name', current_app.config['INSTITUTION_NAME'])
    pdf_buffer = generate_student_id_card_pdf(student, institution_name=inst_name)
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"ID_Card_{student.student_id}.pdf"
    )

@student_bp.route('/subjects')
@login_required
@role_required('student', 'admin')
def subjects():
    student = current_user.student
    if not student:
        flash('Student profile is not linked to this account. Please contact the administrator.', 'warning')
        return redirect(url_for('student.dashboard'))

    _verify_student_query_param(student)

    subject_attendance = student.get_subject_wise_attendance()
    overall_stats = student.calculate_attendance_stats()

    return render_template(
        'student/subjects.html',
        student=student,
        subject_attendance=subject_attendance,
        overall_stats=overall_stats
    )

@student_bp.route('/subjects/<int:subject_id>')
@login_required
@role_required('student', 'admin')
def subject_detail(subject_id):
    student = current_user.student
    if not student:
        flash('Student profile is not linked to this account. Please contact the administrator.', 'warning')
        return redirect(url_for('student.dashboard'))

    _verify_student_query_param(student)

    from app.models.subject import Subject
    subject = Subject.query.get_or_404(subject_id)

    records = student.attendances.filter_by(subject_id=subject_id).order_by(Attendance.date.desc()).all()
    total_classes = len(records)
    present_classes = sum(1 for a in records if a.status in ('Present', 'Late', 'Half Day'))
    absent_classes = sum(1 for a in records if a.status == 'Absent')
    pct = round((present_classes / total_classes * 100), 1) if total_classes > 0 else 0.0

    teacher_names = [t.full_name for t in subject.teachers]
    teacher_str = ", ".join(teacher_names) if teacher_names else "Assigned Faculty"

    stats = {
        'total_classes': total_classes,
        'present_classes': present_classes,
        'absent_classes': absent_classes,
        'attendance_percentage': pct,
        'teacher_name': teacher_str
    }

    return render_template(
        'student/subject_detail.html',
        student=student,
        subject=subject,
        records=records,
        stats=stats
    )
