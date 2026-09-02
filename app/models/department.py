from datetime import datetime
from app.extensions import db

class Department(db.Model):
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False) # e.g. "CS", "ME", "EE"
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    students = db.relationship('Student', backref='department', lazy='dynamic', cascade='all')
    teachers = db.relationship('Teacher', backref='department', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'description': self.description,
            'students_count': self.students.count(),
            'teachers_count': self.teachers.count()
        }

    def __repr__(self):
        return f"<Department {self.code} - {self.name}>"
