import re
from datetime import datetime
from app.extensions import db

def format_semester_name(sem):
    """
    Format semester string into standard display name (e.g. '4' or '4th' -> '4th Semester').
    Handles 'None', 'null', empty strings gracefully by returning 'Not Set'.
    """
    if not sem or not str(sem).strip():
        return 'Not Set'
    s = str(sem).strip()
    if s.lower() in ('not set', 'none', 'null', 'undefined', ''):
        return 'Not Set'

    # If already contains 'semester' (case-insensitive), normalize capitalization
    if 'semester' in s.lower():
        parts = s.split()
        return " ".join(p.capitalize() if p.lower() == 'semester' else p for p in parts)

    # Check if string contains digits (e.g. "4", "4th", "sem 4")
    digits = re.findall(r'\d+', s)
    if digits:
        d = int(digits[0])
        if 11 <= (d % 100) <= 13:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(d % 10, 'th')
        return f"{d}{suffix} Semester"

    return f"{s} Semester"

teacher_subjects = db.Table(
    'teacher_subjects',
    db.Column('teacher_id', db.Integer, db.ForeignKey('teachers.id', ondelete='CASCADE'), primary_key=True),
    db.Column('subject_id', db.Integer, db.ForeignKey('subjects.id', ondelete='CASCADE'), primary_key=True),
    db.Column('assigned_at', db.DateTime, default=datetime.utcnow)
)

class Subject(db.Model):
    __tablename__ = 'subjects'

    id = db.Column(db.Integer, primary_key=True)
    subject_code = db.Column(db.String(32), unique=True, nullable=False, index=True) # e.g. "CS101"
    subject_name = db.Column(db.String(150), nullable=False, index=True) # e.g. "Data Structures"
    description = db.Column(db.Text, nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True)
    course = db.Column(db.String(100), nullable=True) # e.g. "B.Tech Computer Science"
    semester = db.Column(db.String(20), nullable=True) # e.g. "4th"
    session_id = db.Column(db.Integer, db.ForeignKey('academic_sessions.id', ondelete='SET NULL'), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    department = db.relationship('Department', backref=db.backref('subjects', lazy='dynamic'))
    academic_session = db.relationship('AcademicSession', backref=db.backref('subjects', lazy='dynamic'))
    teachers = db.relationship('Teacher', secondary=teacher_subjects, backref=db.backref('assigned_subjects', lazy='dynamic'))

    @property
    def active_teacher_assignments(self):
        """Returns all active TeacherSubjectAssignment records for this subject."""
        from app.models.subject_assignment import TeacherSubjectAssignment
        return TeacherSubjectAssignment.query.filter(
            TeacherSubjectAssignment.subject_id == self.id,
            TeacherSubjectAssignment.is_active != False
        ).all()

    @property
    def assigned_faculty_list(self):
        """
        Returns list of assigned faculty items with teacher details, full name, and formatted semester:
        [{'teacher_id': t_id, 'name': full_name, 'email': email, 'semester': sem, 'section': sec, 'assignment_id': id}]
        Prioritizes the active AcademicSession where applicable to prevent historical sessions from leaking.
        """
        items = []
        seen = set()

        from app.models.session import AcademicSession
        active_session = AcademicSession.query.filter_by(is_active=True).first()

        # 1. Primary: From formal TeacherSubjectAssignment records
        active_asgns = self.active_teacher_assignments

        # If an active session exists, prioritize assignments for this session + general unscoped assignments
        if active_session and active_asgns:
            session_scoped = [a for a in active_asgns if a.session_id == active_session.id]
            unscoped = [a for a in active_asgns if a.session_id is None]
            if session_scoped:
                active_asgns = session_scoped + unscoped

        for asgn in active_asgns:
            if asgn.teacher and asgn.teacher.is_active is not False:
                sem = format_semester_name(asgn.semester or self.semester)
                teacher_name = (
                    asgn.teacher.full_name or
                    (asgn.teacher.user.get_display_name() if asgn.teacher.user else None) or
                    getattr(asgn.teacher, 'name', None) or
                    (f"Prof. {asgn.teacher.employee_id}" if asgn.teacher.employee_id else "Assigned Faculty")
                )
                key = (asgn.teacher_id, sem, asgn.section, asgn.course)
                if key not in seen:
                    seen.add(key)
                    items.append({
                        'teacher_id': asgn.teacher_id,
                        'name': teacher_name,
                        'email': asgn.teacher.email,
                        'semester': sem,
                        'section': asgn.section,
                        'course': asgn.course,
                        'assignment_id': asgn.id,
                        'teacher': asgn.teacher,
                        'session_id': asgn.session_id
                    })

        # 2. Secondary fallback: from legacy/many-to-many relationship ONLY if no formal assignments exist
        if not items:
            for t in self.teachers:
                if t.is_active is not False:
                    sem = format_semester_name(self.semester)
                    teacher_name = (
                        t.full_name or
                        (t.user.get_display_name() if t.user else None) or
                        getattr(t, 'name', None) or
                        (f"Prof. {t.employee_id}" if t.employee_id else "Assigned Faculty")
                    )
                    key = (t.id, sem, None, None)
                    if key not in seen:
                        seen.add(key)
                        items.append({
                            'teacher_id': t.id,
                            'name': teacher_name,
                            'email': t.email,
                            'semester': sem,
                            'section': None,
                            'course': None,
                            'assignment_id': None,
                            'teacher': t,
                            'session_id': None
                        })

        return items

    @property
    def display_semesters(self):
        """
        Returns a deduplicated list of active, formatted semester strings for this subject.
        """
        sems = []
        for f in self.assigned_faculty_list:
            sem = f.get('semester')
            if sem and sem != 'Not Set' and sem not in sems:
                sems.append(sem)
        if not sems and self.semester:
            formatted = format_semester_name(self.semester)
            if formatted != 'Not Set' and formatted not in sems:
                sems.append(formatted)
        return sems

    @property
    def primary_semester(self):
        """
        Returns the primary or first semester string, or 'Not Set'.
        """
        sems = self.display_semesters
        if sems:
            return sems[0]
        if self.semester:
            formatted = format_semester_name(self.semester)
            if formatted != 'Not Set':
                return formatted
        return 'Not Set'

    @property
    def assigned_faculty(self):
        """Returns single faculty name or comma-separated list of assigned faculty names, or 'Not Assigned'."""
        fl = self.assigned_faculty_list
        if not fl:
            return "Not Assigned"
        return ", ".join(f['name'] for f in fl)

    @property
    def faculty(self):
        """Alias for assigned_faculty_list."""
        return self.assigned_faculty_list

    @property
    def total_sessions(self) -> int:
        """
        Returns the number of conducted class days/sessions for this subject.
        Strictly counts DISTINCT conducted dates where attendance_type == 'SUBJECT'.
        1 day with 5, 50, or 100 students = 1 session.
        Uses _cached_total_sessions if pre-calculated in batch to avoid N+1 queries.
        """
        if hasattr(self, '_cached_total_sessions') and self._cached_total_sessions is not None:
            return self._cached_total_sessions
        from app.models.attendance import Attendance
        from sqlalchemy import func
        count = db.session.query(func.count(func.distinct(Attendance.date))).filter(
            Attendance.subject_id == self.id,
            Attendance.attendance_type == 'SUBJECT'
        ).scalar()
        return count or 0

    def to_dict(self):
        faculty = self.assigned_faculty_list
        primary_sem = self.primary_semester
        return {
            'id': self.id,
            'subject_code': self.subject_code,
            'subject_name': self.subject_name,
            'code': self.subject_code,
            'name': self.subject_name,
            'description': self.description,
            'department_id': self.department_id,
            'department_name': self.department.name if self.department else None,
            'department_code': self.department.code if self.department else None,
            'course': self.course,
            'semester': primary_sem if primary_sem != 'Not Set' else (self.semester or None),
            'semesters': self.display_semesters,
            'session_id': self.session_id,
            'session_name': self.academic_session.name if self.academic_session else None,
            'is_active': self.is_active,
            'assigned_faculty': [
                {
                    'id': f['teacher_id'],
                    'name': f['name'],
                    'semester': f['semester'],
                    'section': f.get('section'),
                    'course': f.get('course')
                }
                for f in faculty
            ],
            'teachers': [{'id': t.id, 'name': t.full_name, 'employee_id': t.employee_id} for t in self.teachers],
            'teacher_names': [f['name'] for f in faculty] if faculty else [t.full_name for t in self.teachers],
            'total_sessions': self.total_sessions,
            'attendance_count': self.total_sessions,
            'historical_records_count': self.attendances.count() if hasattr(self, 'attendances') else 0,
            'created_at': self.created_at.strftime('%Y-%m-%d') if self.created_at else None
        }

    def __repr__(self):
        return f"<Subject {self.subject_code} - {self.subject_name}>"
