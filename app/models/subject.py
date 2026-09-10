from datetime import datetime
from app.extensions import db

teacher_subjects = db.Table(
    'teacher_subjects',
    db.Column('teacher_id', db.Integer, db.ForeignKey('teachers.id', ondelete='CASCADE'), primary_key=True),
    db.Column('subject_id', db.Integer, db.ForeignKey('subjects.id', ondelete='CASCADE'), primary_key=True),
    db.Column('assigned_at', db.DateTime, default=datetime.utcnow)
)

class Subject(db.Model):
    __tablename__ = 'subjects'

    id = db.Column(db.Integer, primary_key=True)
    subject_code = db.Column(db.String(32), unique=True, nullable=False, index=True) # e.g. "CS101"
    subject_name = db.Column(db.String(150), nullable=False, index=True) # e.g. "Data Structures"
    description = db.Column(db.Text, nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True)
    course = db.Column(db.String(100), nullable=True) # e.g. "B.Tech Computer Science"
    semester = db.Column(db.String(20), nullable=True) # e.g. "4th"
    session_id = db.Column(db.Integer, db.ForeignKey('academic_sessions.id', ondelete='SET NULL'), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    department = db.relationship('Department', backref=db.backref('subjects', lazy='dynamic'))
    academic_session = db.relationship('AcademicSession', backref=db.backref('subjects', lazy='dynamic'))
    teachers = db.relationship('Teacher', secondary=teacher_subjects, backref=db.backref('assigned_subjects', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'subject_code': self.subject_code,
            'subject_name': self.subject_name,
            'description': self.description,
            'department_id': self.department_id,
            'department_name': self.department.name if self.department else None,
            'department_code': self.department.code if self.department else None,
            'course': self.course,
            'semester': self.semester,
            'session_id': self.session_id,
            'session_name': self.academic_session.name if self.academic_session else None,
            'is_active': self.is_active,
            'teachers': [{'id': t.id, 'name': t.full_name, 'employee_id': t.employee_id} for t in self.teachers],
            'teacher_names': [t.full_name for t in self.teachers],
            'attendance_count': self.attendances.count() if hasattr(self, 'attendances') else 0,
            'created_at': self.created_at.strftime('%Y-%m-%d') if self.created_at else None
        }

    def __repr__(self):
        return f"<Subject {self.subject_code} - {self.subject_name}>"
