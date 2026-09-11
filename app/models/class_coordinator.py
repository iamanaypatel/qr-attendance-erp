from datetime import datetime
from app.extensions import db

class ClassCoordinator(db.Model):
    __tablename__ = 'class_coordinators'

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id', ondelete='CASCADE'), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True)
    course = db.Column(db.String(100), nullable=True) # e.g. "B.Tech Computer Science" or "B.Tech CSE"
    semester = db.Column(db.String(32), nullable=False, index=True) # e.g. "4th" or "4th Semester"
    section = db.Column(db.String(32), nullable=True) # e.g. "A", "B"
    session_id = db.Column(db.Integer, db.ForeignKey('academic_sessions.id', ondelete='SET NULL'), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    teacher = db.relationship('Teacher', backref=db.backref('coordinator_assignments', lazy='dynamic'))
    department = db.relationship('Department', backref=db.backref('coordinator_assignments', lazy='dynamic'))
    academic_session = db.relationship('AcademicSession', backref=db.backref('coordinator_assignments', lazy='dynamic'))

    __table_args__ = (
        db.Index('idx_coordinator_dept_sem_sec', 'department_id', 'semester', 'section', 'is_active'),
    )

    @classmethod
    def assign_coordinator(cls, teacher_id: int, semester: str, department_id: int = None,
                           course: str = None, section: str = None, session_id: int = None,
                           is_active: bool = True):
        """
        Assign a teacher as the active Class Coordinator for the specified class.
        Deactivates any previous active coordinator for the same class context to guarantee
        that there is ONLY ONE active coordinator per class.
        """
        sem_clean = semester.strip() if semester else 'General'
        sec_clean = section.strip() if section else None
        course_clean = course.strip() if course else None

        # Find existing active coordinators for the same class
        q = cls.query.filter_by(semester=sem_clean, is_active=True)
        if department_id is not None:
            q = q.filter_by(department_id=department_id)
        if course_clean:
            q = q.filter_by(course=course_clean)
        if sec_clean:
            q = q.filter_by(section=sec_clean)
        if session_id is not None:
            q = q.filter_by(session_id=session_id)

        existing_active = q.all()
        for old in existing_active:
            if old.teacher_id != teacher_id:
                old.is_active = False
                old.updated_at = datetime.utcnow()

        # Check if this teacher already had an assignment for this class
        same_asgn = cls.query.filter_by(
            teacher_id=teacher_id,
            semester=sem_clean,
            department_id=department_id,
            section=sec_clean,
            course=course_clean,
            session_id=session_id
        ).first()

        if same_asgn:
            same_asgn.is_active = True
            same_asgn.updated_at = datetime.utcnow()
            asgn = same_asgn
        else:
            asgn = cls(
                teacher_id=teacher_id,
                department_id=department_id,
                course=course_clean,
                semester=sem_clean,
                section=sec_clean,
                session_id=session_id,
                is_active=True
            )
            db.session.add(asgn)

        db.session.commit()
        return asgn

    @property
    def class_label(self) -> str:
        dept_part = self.department.code if self.department else (self.course or 'General')
        sem_part = self.semester
        sec_part = f" — Sec {self.section}" if self.section else ""
        return f"{dept_part} — {sem_part}{sec_part}"

    def to_dict(self):
        dept_name = self.department.name if self.department else None
        dept_code = self.department.code if self.department else None
        t_name = self.teacher.full_name if self.teacher else 'Unknown'
        emp_id = self.teacher.employee_id if self.teacher else None

        return {
            'id': self.id,
            'assignment_id': self.id,
            'teacher_id': self.teacher_id,
            'teacher_name': t_name,
            'employee_id': emp_id,
            'department_id': self.department_id,
            'department': dept_name,
            'department_name': dept_name,
            'department_code': dept_code,
            'course': self.course,
            'semester': self.semester,
            'section': self.section,
            'session_id': self.session_id,
            'session_name': self.academic_session.name if self.academic_session else None,
            'class_label': self.class_label,
            'is_active': self.is_active,
            'created_at': self.created_at.strftime('%Y-%m-%d') if self.created_at else None
        }

    def __repr__(self):
        t_name = self.teacher.full_name if self.teacher else self.teacher_id
        return f"<ClassCoordinator Teacher:{t_name} Class:{self.class_label}>"
