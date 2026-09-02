import io
import csv
from datetime import datetime, date, timedelta
from flask import render_template, request, send_file, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app.reports import reports_bp
from app.models.student import Student
from app.models.department import Department
from app.models.attendance import Attendance
from app.models.settings import SystemSetting
from app.utils.decorators import role_required
from app.utils.mailer import send_email
from app.reports.excel_export import generate_attendance_excel
from app.reports.pdf_export import generate_attendance_pdf

def build_filtered_query(args):
    query = Attendance.query.join(Student)

    from_date_str = args.get('from_date', '').strip()
    to_date_str = args.get('to_date', '').strip()
    dept_id = args.get('dept', type=int)
    student_query = args.get('student', '').strip()
    status = args.get('status', '').strip()
    method = args.get('method', '').strip()

    filter_desc = []

    if from_date_str:
        try:
            d1 = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            query = query.filter(Attendance.date >= d1)
            filter_desc.append(f"From {d1}")
        except ValueError:
            pass

    if to_date_str:
        try:
            d2 = datetime.strptime(to_date_str, '%Y-%m-%d').date()
            query = query.filter(Attendance.date <= d2)
            filter_desc.append(f"To {d2}")
        except ValueError:
            pass

    if dept_id:
        query = query.filter(Student.department_id == dept_id)
        dept = Department.query.get(dept_id)
        if dept:
            filter_desc.append(f"Dept: {dept.code}")

    if student_query:
        query = query.filter(
            (Student.full_name.ilike(f"%{student_query}%")) |
            (Student.student_id.ilike(f"%{student_query}%")) |
            (Student.roll_number.ilike(f"%{student_query}%"))
        )
        filter_desc.append(f"Student: '{student_query}'")

    if status:
        query = query.filter(Attendance.status == status)
        filter_desc.append(f"Status: {status}")

    if method:
        query = query.filter(Attendance.method == method)
        filter_desc.append(f"Method: {method}")

    summary_str = ", ".join(filter_desc) if filter_desc else "All Records"
    return query.order_by(Attendance.date.desc(), Attendance.time_in.desc().nullslast()), summary_str

@reports_bp.route('/')
@login_required
@role_required('admin', 'teacher')
def index():
    page = request.args.get('page', 1, type=int)
    query, filter_desc = build_filtered_query(request.args)

    pagination = query.paginate(page=page, per_page=20, error_out=False)
    departments = Department.query.order_by(Department.name).all()

    # Precalculate summary stats on filtered dataset
    all_filtered = query.all()
    total = len(all_filtered)
    present_cnt = sum(1 for r in all_filtered if r.status in ('Present', 'Late', 'Half Day'))
    absent_cnt = sum(1 for r in all_filtered if r.status == 'Absent')
    rate = round((present_cnt / total * 100), 1) if total > 0 else 0.0

    stats = {
        'total': total,
        'present': present_cnt,
        'absent': absent_cnt,
        'rate': rate
    }

    return render_template(
        'reports/index.html',
        pagination=pagination,
        records=pagination.items,
        departments=departments,
        stats=stats,
        filter_summary=filter_desc,
        args=request.args
    )

@reports_bp.route('/export/excel')
@login_required
@role_required('admin', 'teacher')
def export_excel():
    query, filter_desc = build_filtered_query(request.args)
    records = query.all()

    inst_name = SystemSetting.get_setting('institution_name', current_app.config['INSTITUTION_NAME'])
    excel_buffer = generate_attendance_excel(records, institution_name=inst_name)

    filename = f"Attendance_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        excel_buffer,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

@reports_bp.route('/export/pdf')
@login_required
@role_required('admin', 'teacher')
def export_pdf():
    query, filter_desc = build_filtered_query(request.args)
    records = query.all()

    inst_name = SystemSetting.get_setting('institution_name', current_app.config['INSTITUTION_NAME'])
    pdf_buffer = generate_attendance_pdf(records, institution_name=inst_name, filter_summary=filter_desc)

    filename = f"Attendance_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

@reports_bp.route('/export/csv')
@login_required
@role_required('admin', 'teacher')
def export_csv():
    query, _ = build_filtered_query(request.args)
    records = query.all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Headers
    writer.writerow([
        "Student ID", "Student Name", "Department", "Course", "Semester",
        "Date", "Time In", "Time Out", "Status", "Method", "Marked By", "Remarks"
    ])

    for r in records:
        s = r.student
        writer.writerow([
            s.student_id if s else "",
            s.full_name if s else "",
            s.department.code if (s and s.department) else "",
            s.course if s else "",
            s.semester if s else "",
            r.date.strftime('%Y-%m-%d') if r.date else "",
            r.time_in.strftime('%I:%M %p') if r.time_in else "",
            r.time_out.strftime('%I:%M %p') if r.time_out else "",
            r.status,
            r.method,
            r.marker.username if r.marker else "System",
            r.remarks or ""
        ])

    mem = io.BytesIO()
    mem.write(output.getvalue().encode('utf-8'))
    mem.seek(0)

    filename = f"Attendance_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return send_file(
        mem,
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )

@reports_bp.route('/print')
@login_required
@role_required('admin', 'teacher')
def print_view():
    query, filter_desc = build_filtered_query(request.args)
    records = query.all()

    inst_name = SystemSetting.get_setting('institution_name', current_app.config['INSTITUTION_NAME'])
    total = len(records)
    present_cnt = sum(1 for r in records if r.status in ('Present', 'Late', 'Half Day'))
    absent_cnt = sum(1 for r in records if r.status == 'Absent')
    rate = round((present_cnt / total * 100), 1) if total > 0 else 0.0

    stats = {'total': total, 'present': present_cnt, 'absent': absent_cnt, 'rate': rate}

    return render_template(
        'reports/print_view.html',
        records=records,
        stats=stats,
        institution_name=inst_name,
        filter_summary=filter_desc,
        now=datetime.now()
    )

@reports_bp.route('/email', methods=['POST'])
@login_required
@role_required('admin')
def email_report():
    recipient = request.form.get('recipient_email', '').strip()
    export_format = request.form.get('format', 'pdf').strip().lower()

    if not recipient:
        flash('Recipient email is required.', 'danger')
        return redirect(url_for('reports.index'))

    query, filter_desc = build_filtered_query(request.args)
    records = query.all()

    inst_name = SystemSetting.get_setting('institution_name', current_app.config['INSTITUTION_NAME'])
    subject = f"Attendance Report: {inst_name} ({date.today()})"

    html_content = f"""
    <h2>{inst_name} — Attendance Report</h2>
    <p>Please find attached the official attendance report.</p>
    <p><strong>Filters applied:</strong> {filter_desc}</p>
    <p><strong>Total records:</strong> {len(records)}</p>
    """

    attachment = None
    if export_format == 'excel':
        excel_buf = generate_attendance_excel(records, institution_name=inst_name)
        attachment = (f"Attendance_{date.today()}.xlsx", excel_buf.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    else:
        pdf_buf = generate_attendance_pdf(records, institution_name=inst_name, filter_summary=filter_desc)
        attachment = (f"Attendance_{date.today()}.pdf", pdf_buf.getvalue(), 'application/pdf')

    sent = send_email(subject, [recipient], html_content, attachment=attachment)
    if sent:
        flash(f"Report dispatched to {recipient} successfully.", 'success')
    else:
        flash(f"Could not send email. Please check SMTP settings in .env configuration.", 'warning')

    return redirect(url_for('reports.index'))
