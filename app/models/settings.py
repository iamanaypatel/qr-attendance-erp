from datetime import datetime
from app.extensions import db

class SystemSetting(db.Model):
    __tablename__ = 'system_settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=True)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @classmethod
    def get_setting(cls, key: str, default: str = None) -> str:
        record = cls.query.filter_by(key=key).first()
        val = record.value if record and record.value is not None else default

        # Auto-heal legacy database settings to Dr. Virendra Swarup Memorial Trust Group of Institutions
        if key == 'institution_name':
            if not val or 'Apex' in val or 'Technology' in val:
                val = "Dr. Virendra Swarup Memorial Trust Group of Institutions"
                try:
                    if record:
                        record.value = val
                    else:
                        db.session.add(cls(key=key, value=val, description="Full legal institution name"))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
        elif key == 'institution_email':
            if not val or 'apex' in val:
                val = "contact@vsmt.edu.in"
                try:
                    if record:
                        record.value = val
                    else:
                        db.session.add(cls(key=key, value=val, description="Official administrative contact email"))
                    db.session.commit()
                except Exception:
                    db.session.rollback()

        return val

    @classmethod
    def set_setting(cls, key: str, value: str, description: str = None):
        record = cls.query.filter_by(key=key).first()
        if record:
            record.value = str(value)
            if description:
                record.description = description
        else:
            record = cls(key=key, value=str(value), description=description)
            db.session.add(record)
        db.session.commit()
        return record

    def __repr__(self):
        return f"<SystemSetting {self.key}={self.value}>"
