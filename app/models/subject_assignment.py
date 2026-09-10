from datetime import datetime
from app.extensions import db

class TeacherSubjectAssignment(db.Model):
    __tablename__ = 'teacher_subject_assignments'

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id', ondelete='CASCADE'), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, index=True)
    semester = db.Column(db.String(32), nullable=False, index=True) # e.g. "4th Semester" or "4th"
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True)
    course = db.Column(db.String(100), nullable=True) # e.g. "B.Tech Computer Science"
    section = db.Column(db.String(32), nullable=True) # e.g. "A", "B"
    session_id = db.Column(db.Integer, db.ForeignKey('academic_sessions.id', ondelete='SET NULL'), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    teacher = db.relationship('Teacher', backref=db.backref('subject_assignments', lazy='dynamic'))
    subject = db.relationship('Subject', backref=db.backref('teacher_assignments', lazy='dynamic'))
    department = db.relationship('Department', backref=db.backref('subject_assignments', lazy='dynamic'))
    academic_session = db.relationship('AcademicSession', backref=db.backref('subject_assignments', lazy='dynamic'))

    __table_args__ = (
        db.Index('idx_teacher_subject_sem_sec', 'teacher_id', 'subject_id', 'semester', 'section'),
    )

    def to_dict(self):
        dept_name = self.department.name if self.department else (self.subject.department.name if (self.subject and self.subject.department) else None)
        course_name = self.course or (self.subject.course if self.subject else None)
        return {
            'id': self.id,
            'assignment_id': self.id,
            'teacher_id': self.teacher_id,
            'teacher_name': self.teacher.full_name if self.teacher else 'Unknown',
            'employee_id': self.teacher.employee_id if self.teacher else None,
            'subject_id': self.subject_id,
            'subject_code': self.subject.subject_code if self.subject else None,
            'subject_name': self.subject.subject_name if self.subject else None,
            'code': self.subject.subject_code if self.subject else None,
            'name': self.subject.subject_name if self.subject else None,
            'semester': self.semester,
            'department_id': self.department_id,
            'department': dept_name,
            'department_name': dept_name,
            'course': course_name,
            'section': self.section,
            'is_active': self.is_active,
            'created_at': self.created_at.strftime('%Y-%m-%d') if self.created_at else None
        }

    def __repr__(self):
        t_name = self.teacher.full_name if self.teacher else self.teacher_id
        s_code = self.subject.subject_code if self.subject else self.subject_id
        return f"<TeacherSubjectAssignment Teacher:{t_name} Subject:{s_code} Sem:{self.semester}>"
