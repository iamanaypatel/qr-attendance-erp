from datetime import datetime, date
from app.extensions import db

class Attendance(db.Model):
    __tablename__ = 'attendances'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
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

    # Enforce database-level uniqueness: one record per student per date
    __table_args__ = (
        db.UniqueConstraint('student_id', 'date', name='uq_student_date_attendance'),
        db.Index('idx_attendance_date_student', 'date', 'student_id'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student.student_id if self.student else None,
            'student_name': self.student.full_name if self.student else None,
            'department': self.student.department.name if (self.student and self.student.department) else None,
            'date': self.date.strftime('%Y-%m-%d') if self.date else None,
            'time_in': self.time_in.strftime('%I:%M %p') if self.time_in else None,
            'time_out': self.time_out.strftime('%I:%M %p') if self.time_out else None,
            'status': self.status,
            'method': self.method,
            'marked_by': self.marker.get_display_name() if self.marker else 'System',
            'remarks': self.remarks
        }

    def __repr__(self):
        return f"<Attendance Student:{self.student_id} Date:{self.date} Status:{self.status}>"
