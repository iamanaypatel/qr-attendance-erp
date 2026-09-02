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
        return record.value if record and record.value is not None else default

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
