from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db, login_manager

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student') # 'admin', 'teacher', 'student'
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    student_profile = db.relationship('Student', backref='user', uselist=False, cascade='all, delete-orphan')
    teacher_profile = db.relationship('Teacher', backref='user', uselist=False, cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def has_role(self, *roles: str) -> bool:
        return self.role in roles

    @property
    def is_admin(self) -> bool:
        return self.role == 'admin'

    @property
    def is_teacher(self) -> bool:
        return self.role == 'teacher'

    @property
    def is_student(self) -> bool:
        return self.role == 'student'

    @property
    def student(self):
        """Convenience alias for student_profile with auto-healing resolution."""
        if self.student_profile:
            return self.student_profile
        if self.role == 'student':
            from app.models.student import Student
            from sqlalchemy import func
            match = Student.query.filter(
                (func.lower(Student.student_id) == func.lower(self.username)) |
                (func.lower(Student.roll_number) == func.lower(self.username)) |
                (func.lower(Student.email) == func.lower(self.email))
            ).first()
            if match:
                match.user_id = self.id
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                return match
        return None

    def get_display_name(self) -> str:
        s = self.student
        if self.role == 'student' and s:
            return s.full_name
        if self.role == 'teacher' and self.teacher_profile:
            return self.teacher_profile.full_name
        return self.username

    def __repr__(self) -> str:
        return f"<User {self.username} [{self.role}]>"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
