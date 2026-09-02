from datetime import datetime, date
import secrets
from app.extensions import db

class Student(db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, unique=True)
    student_id = db.Column(db.String(32), unique=True, nullable=False, index=True) # e.g. STU2026001
    full_name = db.Column(db.String(120), nullable=False)
    father_name = db.Column(db.String(120), nullable=True)
    mother_name = db.Column(db.String(120), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    phone = db.Column(db.String(20), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(20), nullable=True) # Male, Female, Other
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='RESTRICT'), nullable=False)
    course = db.Column(db.String(100), nullable=False) # e.g. "B.Tech Computer Science"
    semester = db.Column(db.String(20), nullable=False) # e.g. "4th"
    section = db.Column(db.String(10), nullable=True) # e.g. "A"
    roll_number = db.Column(db.String(50), nullable=False, index=True)
    address = db.Column(db.Text, nullable=True)
    photo = db.Column(db.String(255), nullable=True) # Filename in static/uploads
    qr_token = db.Column(db.String(64), unique=True, nullable=False, index=True) # Cryptographic secure token
    admission_date = db.Column(db.Date, default=date.today, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    attendances = db.relationship('Attendance', backref='student', lazy='dynamic', cascade='all, delete-orphan')

    @staticmethod
    def generate_qr_token() -> str:
        """Generate a cryptographically secure, URL-safe random token for QR code encoding."""
        return secrets.token_urlsafe(32)

    def calculate_attendance_stats(self, start_date=None, end_date=None):
        """Calculate total classes, present, absent, and attendance percentage safely."""
        query = self.attendances
        if start_date:
            query = query.filter(self.attendances.property.mapper.class_.date >= start_date)
        if end_date:
            query = query.filter(self.attendances.property.mapper.class_.date <= end_date)

        records = query.all()
        total_sessions = len(records)
        present_count = sum(1 for a in records if a.status in ('Present', 'Late', 'Half Day'))
        absent_count = sum(1 for a in records if a.status == 'Absent')

        # Handle zero applicable sessions safely
        percentage = round((present_count / total_sessions * 100), 2) if total_sessions > 0 else 0.0

        return {
            'total_sessions': total_sessions,
            'present_count': present_count,
            'absent_count': absent_count,
            'percentage': percentage
        }

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'department_id': self.department_id,
            'department_name': self.department.name if self.department else None,
            'department_code': self.department.code if self.department else None,
            'course': self.course,
            'semester': self.semester,
            'section': self.section,
            'roll_number': self.roll_number,
            'photo': self.photo,
            'is_active': self.is_active
        }

    def __repr__(self):
        return f"<Student {self.student_id} - {self.full_name}>"
