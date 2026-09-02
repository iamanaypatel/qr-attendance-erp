from datetime import datetime
from flask import request
from app.extensions import db

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    action = db.Column(db.String(100), nullable=False, index=True) # e.g. "MANUAL_ATTENDANCE", "STUDENT_DELETE"
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    @classmethod
    def log(cls, action: str, details: str = None, user_id: int = None, commit: bool = True):
        try:
            client_ip = None
            try:
                if request:
                    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
                    if client_ip and ',' in client_ip:
                        client_ip = client_ip.split(',')[0].strip()
            except Exception:
                client_ip = '127.0.0.1'

            entry = cls(
                user_id=user_id,
                action=action,
                details=details,
                ip_address=client_ip
            )
            db.session.add(entry)
            if commit:
                db.session.commit()
            return entry
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            return None

    def __repr__(self):
        return f"<AuditLog {self.action} by User:{self.user_id} at {self.created_at}>"
