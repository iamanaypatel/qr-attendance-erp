from datetime import datetime
from app.extensions import db

class Teacher(db.Model):
    __tablename__ = 'teachers'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    employee_id = db.Column(db.String(32), unique=True, nullable=False, index=True) # e.g. TCH101
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True)
    designation = db.Column(db.String(100), default='Lecturer', nullable=False) # e.g. Professor, Assistant Professor, HOD
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def is_assigned_to_subject(self, subject_id: int, semester: str = None) -> bool:
        """Check if teacher is actively assigned to the given subject_id (and optionally semester)."""
        if not subject_id:
            return False
        from app.models.subject_assignment import TeacherSubjectAssignment
        query = self.subject_assignments.filter_by(subject_id=subject_id, is_active=True)
        if semester and semester.strip():
            query = query.filter(TeacherSubjectAssignment.semester.ilike(semester.strip()))
        if query.first() is not None:
            return True
        # Fallback to secondary association table for legacy setups
        if hasattr(self, 'assigned_subjects') and self.assigned_subjects.filter_by(id=subject_id, is_active=True).first() is not None:
            return True
        return False

    def get_active_assignments(self):
        """Returns list of active TeacherSubjectAssignment objects."""
        assignments = self.subject_assignments.filter_by(is_active=True).all()
        if not assignments and hasattr(self, 'assigned_subjects'):
            # Fallback to secondary association table if no explicit TeacherSubjectAssignment exists
            legacy_subs = self.assigned_subjects.filter_by(is_active=True).all()
            if legacy_subs:
                from app.models.subject_assignment import TeacherSubjectAssignment
                for sub in legacy_subs:
                    sem = sub.semester or 'General'
                    existing = TeacherSubjectAssignment.query.filter_by(teacher_id=self.id, subject_id=sub.id, semester=sem).first()
                    if not existing:
                        existing = TeacherSubjectAssignment(
                            teacher_id=self.id,
                            subject_id=sub.id,
                            semester=sem,
                            department_id=sub.department_id or self.department_id,
                            course=sub.course,
                            is_active=True
                        )
                        db.session.add(existing)
                db.session.commit()
                assignments = self.subject_assignments.filter_by(is_active=True).all()
        return assignments

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'department_id': self.department_id,
            'department_name': self.department.name if self.department else None,
            'designation': self.designation,
            'is_active': self.is_active
        }

    def __repr__(self):
        return f"<Teacher {self.employee_id} - {self.full_name}>"
