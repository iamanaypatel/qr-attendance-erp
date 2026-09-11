from datetime import datetime
from app.extensions import db

class AcademicSession(db.Model):
    __tablename__ = 'academic_sessions'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False) # e.g. "2025-2026"
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        def _fmt(d):
            if not d:
                return ''
            if hasattr(d, 'strftime'):
                return d.strftime('%Y-%m-%d')
            return str(d)

        return {
            'id': self.id,
            'name': self.name,
            'start_date': _fmt(self.start_date),
            'end_date': _fmt(self.end_date),
            'is_active': self.is_active
        }

    def __repr__(self):
        return f"<AcademicSession {self.name} [{'Active' if self.is_active else 'Inactive'}]>"
