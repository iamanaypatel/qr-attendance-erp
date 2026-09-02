from datetime import datetime
from app.extensions import db

class Holiday(db.Model):
    __tablename__ = 'holidays'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    date = db.Column(db.Date, unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'date': self.date.strftime('%Y-%m-%d'),
            'description': self.description
        }

    def __repr__(self):
        return f"<Holiday {self.title} on {self.date}>"
