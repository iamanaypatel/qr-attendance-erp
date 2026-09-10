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

    def is_assigned_to_subject(self, subject_id: int) -> bool:
        """Check if teacher is assigned to the given subject_id."""
        if not subject_id:
            return False
        return self.assigned_subjects.filter_by(id=subject_id).first() is not None

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
