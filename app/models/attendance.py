from datetime import datetime, date
from app.extensions import db

class Attendance(db.Model):
    __tablename__ = 'attendances'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='SET NULL'), nullable=True, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id', ondelete='SET NULL'), nullable=True, index=True)
    date = db.Column(db.Date, default=date.today, nullable=False, index=True)
    time_in = db.Column(db.Time, nullable=True)
    time_out = db.Column(db.Time, nullable=True)
    status = db.Column(db.String(20), default='Present', nullable=False) # 'Present', 'Absent', 'Late', 'Half Day'
    marked_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    method = db.Column(db.String(20), default='QR', nullable=False) # 'QR', 'Manual', 'Admin'
    remarks = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    marker = db.relationship('User', foreign_keys=[marked_by], backref='marked_attendances')
    subject = db.relationship('Subject', foreign_keys=[subject_id], backref=db.backref('attendances', lazy='dynamic'))
    teacher = db.relationship('Teacher', foreign_keys=[teacher_id], backref=db.backref('attendances_marked', lazy='dynamic'))

    # Enforce database-level uniqueness: one record per student per subject per date
    __table_args__ = (
        db.UniqueConstraint('student_id', 'date', 'subject_id', name='uq_student_date_subject_attendance'),
        db.Index('idx_attendance_date_student_subject', 'date', 'student_id', 'subject_id'),
    )

    def to_dict(self):
        duration_str = None
        if self.time_in and self.time_out:
            t_in = datetime.combine(self.date, self.time_in)
            t_out = datetime.combine(self.date, self.time_out)
            diff = t_out - t_in
            total_sec = int(diff.total_seconds())
            if total_sec >= 0:
                hours = total_sec // 3600
                minutes = (total_sec % 3600) // 60
                duration_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

        s_name = self.student.full_name if self.student else "Unknown Student"
        s_id = self.student.student_id if self.student else None
        s_roll = self.student.roll_number if self.student else None
        s_dept = self.student.department.name if (self.student and self.student.department) else None
        s_dept_code = self.student.department.code if (self.student and self.student.department) else None
        s_course = self.student.course if self.student else None
        s_photo = self.student.photo if self.student else None

        t_name = self.teacher.full_name if self.teacher else (self.marker.get_display_name() if self.marker else 'System')

        return {
            'id': self.id,
            'student_id': s_id,
            'student_name': s_name,
            'full_name': s_name,
            'roll_number': s_roll,
            'department': s_dept,
            'department_code': s_dept_code,
            'course': s_course,
            'photo': s_photo,
            'subject_id': self.subject_id,
            'subject_code': self.subject.subject_code if self.subject else None,
            'subject_name': self.subject.subject_name if self.subject else None,
            'teacher_id': self.teacher_id,
            'teacher_name': t_name,
            'student': {
                'id': self.student.id if self.student else None,
                'student_id': s_id,
                'full_name': s_name,
                'roll_number': s_roll,
                'department_name': s_dept,
                'department_code': s_dept_code,
                'course': s_course,
                'photo': s_photo
            } if self.student else None,
            'date': self.date.strftime('%Y-%m-%d') if self.date else None,
            'time_in': self.time_in.strftime('%I:%M %p') if self.time_in else None,
            'time_out': self.time_out.strftime('%I:%M %p') if self.time_out else None,
            'duration': duration_str,
            'status': self.status,
            'method': self.method,
            'marked_by': self.marker.get_display_name() if self.marker else 'System',
            'remarks': self.remarks
        }

    def __repr__(self):
        return f"<Attendance Student:{self.student_id} Date:{self.date} Status:{self.status}>"
