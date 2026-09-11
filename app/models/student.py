from datetime import datetime, date
import secrets
from app.extensions import db

class Student(db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, unique=True)
    student_id = db.Column(db.String(32), unique=True, nullable=False, index=True) # e.g. STU2026001
    full_name = db.Column(db.String(120), nullable=False)
    father_name = db.Column(db.String(120), nullable=True)
    mother_name = db.Column(db.String(120), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    phone = db.Column(db.String(20), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(20), nullable=True) # Male, Female, Other
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='RESTRICT'), nullable=False)
    course = db.Column(db.String(100), nullable=False) # e.g. "B.Tech Computer Science"
    semester = db.Column(db.String(20), nullable=False) # e.g. "4th"
    section = db.Column(db.String(10), nullable=True) # e.g. "A"
    roll_number = db.Column(db.String(50), nullable=False, index=True)
    address = db.Column(db.Text, nullable=True)
    photo = db.Column(db.String(255), nullable=True) # Filename in static/uploads
    qr_token = db.Column(db.String(64), unique=True, nullable=False, index=True) # Cryptographic secure token
    admission_date = db.Column(db.Date, default=date.today, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    attendances = db.relationship('Attendance', backref='student', lazy='dynamic', cascade='all, delete-orphan')

    @staticmethod
    def generate_qr_token() -> str:
        """Generate a cryptographically secure, URL-safe random token for QR code encoding."""
        return secrets.token_urlsafe(32)

    def calculate_attendance_stats(self, start_date=None, end_date=None, attendance_type=None):
        """
        Calculate overall daily (General) attendance stats, or stats for specified type.
        Separates General Attendance from Subject-wise Attendance so a student's
        overall percentage is NOT inflated simply because they attended 5 subjects in 1 day.
        """
        from app.models.attendance import Attendance

        query = self.attendances
        if attendance_type:
            query = query.filter(Attendance.attendance_type == attendance_type)
        else:
            # Strictly use GENERAL attendance, never pollute with SUBJECT or LEGACY
            has_general = self.attendances.filter(Attendance.attendance_type == 'GENERAL').first() is not None
            if has_general:
                query = query.filter(Attendance.attendance_type == 'GENERAL')
            else:
                # Fallback before migration: records with no subject, excluding LEGACY
                query = query.filter(
                    Attendance.subject_id.is_(None),
                    Attendance.attendance_type != 'LEGACY'
                )

        if start_date:
            query = query.filter(Attendance.date >= start_date)
        if end_date:
            query = query.filter(Attendance.date <= end_date)

        records = query.all()
        # Group by date to strictly guarantee ONE student session per date
        records_by_date = {}
        for a in records:
            if a.date not in records_by_date:
                records_by_date[a.date] = a
            elif a.status in ('Present', 'Late', 'Half Day'):
                records_by_date[a.date] = a

        unique_records = list(records_by_date.values())
        total_sessions = len(unique_records)
        present_count = sum(1 for a in unique_records if a.status in ('Present', 'Late', 'Half Day'))
        absent_count = sum(1 for a in unique_records if a.status == 'Absent')

        # Handle zero applicable sessions safely
        percentage = round((present_count / total_sessions * 100), 2) if total_sessions > 0 else 0.0

        return {
            'total_sessions': total_sessions,
            'present_count': present_count,
            'absent_count': absent_count,
            'percentage': percentage
        }

    def get_subject_wise_attendance(self, start_date=None, end_date=None):
        """Calculate subject-wise attendance statistics for this student."""
        from app.models.subject import Subject
        from app.models.attendance import Attendance

        query = self.attendances.filter(
            Attendance.attendance_type == 'SUBJECT',
            Attendance.subject_id.isnot(None)
        )
        if start_date:
            query = query.filter(Attendance.date >= start_date)
        if end_date:
            query = query.filter(Attendance.date <= end_date)
        records = query.all()

        records_by_subject = {}
        for a in records:
            records_by_subject.setdefault(a.subject_id, []).append(a)

        # Subjects associated with student's department & semester (direct or through assignments)
        dept_subjects_dict = {}
        if self.department_id:
            active_dept_subjects = Subject.query.filter(
                (Subject.department_id == self.department_id) | (Subject.department_id.is_(None)),
                Subject.is_active == True
            ).all()
            for s in active_dept_subjects:
                match_sem = False
                if not s.semester or not self.semester or s.semester.strip().lower() == self.semester.strip().lower():
                    match_sem = True
                elif hasattr(s, 'display_semesters') and s.display_semesters:
                    for ds in s.display_semesters:
                        if self.semester and ds.strip().lower() == self.semester.strip().lower():
                            match_sem = True
                            break
                if match_sem:
                    dept_subjects_dict[s.id] = s

        all_subject_ids = set(dept_subjects_dict.keys()) | {sid for sid in records_by_subject.keys() if sid is not None}

        results = []
        for sid in sorted(all_subject_ids):
            subject = dept_subjects_dict.get(sid) or Subject.query.get(sid)
            if not subject:
                continue
            sub_records = records_by_subject.get(sid, [])

            # Compute total conducted classes vs student present classes
            total_conducted_query = Attendance.query.filter(
                Attendance.subject_id == subject.id,
                Attendance.attendance_type == 'SUBJECT'
            )
            if self.semester:
                total_conducted_query = total_conducted_query.filter(
                    (Attendance.semester.ilike(self.semester.strip())) | (Attendance.semester.is_(None))
                )
            if start_date:
                total_conducted_query = total_conducted_query.filter(Attendance.date >= start_date)
            if end_date:
                total_conducted_query = total_conducted_query.filter(Attendance.date <= end_date)
            conducted_dates = total_conducted_query.with_entities(Attendance.date).distinct().count()

            total = max(len(sub_records), conducted_dates)
            present = sum(1 for a in sub_records if a.status in ('Present', 'Late', 'Half Day'))
            absent = max(0, total - present)
            pct = round((present / total * 100), 1) if total > 0 else 0.0

            assigned_teachers = [t['name'] for t in getattr(subject, 'assigned_faculty_list', [])]
            if not assigned_teachers and sub_records:
                assigned_teachers = [a.teacher.full_name for a in sub_records if a.teacher]
            if not assigned_teachers and subject.teachers:
                assigned_teachers = [t.full_name for t in subject.teachers]
            teacher_str = ", ".join(dict.fromkeys(assigned_teachers)) if assigned_teachers else "Faculty"

            results.append({
                'subject_id': subject.id,
                'subject_code': subject.subject_code,
                'subject_name': subject.subject_name,
                'teacher_name': teacher_str,
                'total_classes': total,
                'present_classes': present,
                'absent_classes': absent,
                'attendance_percentage': pct
            })

        # Also include general attendance if records exist without a subject_id
        if None in records_by_subject and records_by_subject[None]:
            sub_records = records_by_subject[None]
            total = len(sub_records)
            present = sum(1 for a in sub_records if a.status in ('Present', 'Late', 'Half Day'))
            absent = sum(1 for a in sub_records if a.status == 'Absent')
            pct = round((present / total * 100), 1) if total > 0 else 0.0
            results.append({
                'subject_id': None,
                'subject_code': 'GEN',
                'subject_name': 'General Campus Attendance',
                'teacher_name': 'Campus Admin',
                'total_classes': total,
                'present_classes': present,
                'absent_classes': absent,
                'attendance_percentage': pct
            })

        return results

    @property
    def photo_url(self) -> str | None:
        """Returns the public browser URL for the student's photo with a cache-busting timestamp."""
        if not self.photo:
            return None
        from app.utils.photo import get_student_photo_url
        return get_student_photo_url(self.photo, updated_at=self.updated_at)

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'department_id': self.department_id,
            'department_name': self.department.name if self.department else None,
            'department_code': self.department.code if self.department else None,
            'course': self.course,
            'semester': self.semester,
            'section': self.section,
            'roll_number': self.roll_number,
            'photo': self.photo,
            'photo_url': self.photo_url,
            'qr_token': self.qr_token,
            'is_active': self.is_active
        }

    def __repr__(self):
        return f"<Student {self.student_id} - {self.full_name}>"

