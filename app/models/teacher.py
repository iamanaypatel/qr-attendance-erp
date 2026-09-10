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
        assignments = self.subject_assignments.filter_by(subject_id=subject_id, is_active=True).all()
        if not assignments:
            # Fallback to secondary association table for legacy setups
            if hasattr(self, 'assigned_subjects') and self.assigned_subjects.filter_by(id=subject_id, is_active=True).first() is not None:
                return True
            return False

        if semester and semester.strip():
            import re
            sem_clean = semester.strip().lower()
            req_digits = re.findall(r'\d+', sem_clean)
            # If an assignment matches the semester (exact, substring, or digit match e.g. '4th' vs '4th Semester')
            for asgn in assignments:
                if not asgn.semester:
                    return True
                asgn_sem = asgn.semester.strip().lower()
                if asgn_sem == sem_clean or sem_clean in asgn_sem or asgn_sem in sem_clean:
                    return True
                asgn_digits = re.findall(r'\d+', asgn_sem)
                if req_digits and asgn_digits and req_digits == asgn_digits:
                    return True
            # Explicit semester was specified and teacher is not assigned to this semester
            return False

        # Teacher has active assignment for this subject when semester is not specified
        return True

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
