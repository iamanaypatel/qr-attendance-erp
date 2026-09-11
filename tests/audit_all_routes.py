import os
import sys
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.subject import Subject
from app.models.session import AcademicSession

app = create_app('development')

def audit():
    errors = []
    print("Starting Comprehensive Route Audit on Development DB...")
    
    with app.test_client() as client:
        with app.app_context():
            # Ensure users exist for testing
            admin = User.query.filter_by(role='admin').first()
            teacher_user = User.query.filter_by(role='teacher').first()
            student_user = User.query.filter_by(role='student').first()
            
            student = Student.query.first()
            teacher = Teacher.query.first()
            subject = Subject.query.first()
            session_obj = AcademicSession.query.first()
            
            student_id = student.id if student else 1
            teacher_id = teacher.id if teacher else 1
            subject_id = subject.id if subject else 1
            session_id = session_obj.id if session_obj else 1

        # ==========================================
        # 1. ADMIN ROUTES AUDIT
        # ==========================================
        client.post('/auth/login', data={'identity': 'admin', 'password': 'Admin@1234'})
        admin_routes = [
            ('/admin/dashboard', 'GET'),
            ('/admin/students', 'GET'),
            (f'/admin/students/{student_id}', 'GET'),
            (f'/admin/students/{student_id}/edit', 'GET'),
            (f'/admin/students/{student_id}/credentials', 'GET'),
            (f'/admin/students/{student_id}/photo', 'GET'),
            ('/admin/students/create', 'GET'),
            ('/admin/teachers', 'GET'),
            (f'/admin/teachers/{teacher_id}/edit', 'GET'),
            (f'/admin/teachers/{teacher_id}/credentials', 'GET'),
            ('/admin/teachers/create', 'GET'),
            ('/admin/subjects', 'GET'),
            ('/admin/subjects/create', 'GET'),
            (f'/admin/subjects/{subject_id}/edit', 'GET'),
            (f'/admin/subjects/{subject_id}/assign-teachers', 'GET'),
            ('/admin/subject-assignments', 'GET'),
            ('/admin/subject-assignments/create', 'GET'),
            ('/admin/class-coordinators', 'GET'),
            ('/admin/class-coordinators/assign', 'GET'),
            ('/admin/settings', 'GET'),
            (f'/admin/sessions/{session_id}/json', 'GET'),
            ('/admin/departments', 'GET'),
            ('/admin/qr-generator', 'GET'),
            ('/attendance/calendar', 'GET'),
            ('/attendance/manual', 'GET'),
            ('/attendance/scanner', 'GET'),
            ('/reports/', 'GET'),
            ('/reports/email', 'GET'),
            ('/reports/print', 'GET'),
        ]

        for path, method in admin_routes:
            try:
                resp = client.open(path, method=method)
                if resp.status_code == 500:
                    errors.append((path, method, 'Admin', resp.status_code, resp.data[:500].decode('utf-8', errors='replace')))
                    print(f"❌ 500 ERROR: [Admin] {method} {path}")
                else:
                    print(f"✅ {resp.status_code}: [Admin] {method} {path}")
            except Exception as e:
                errors.append((path, method, 'Admin', 'EXCEPTION', str(e)))
                print(f"🔥 EXCEPTION: [Admin] {method} {path} -> {e}")

        client.get('/auth/logout')

        # ==========================================
        # 2. TEACHER ROUTES AUDIT
        # ==========================================
        client.post('/auth/login', data={'identity': 'teacher', 'password': 'Teacher@1234'})
        teacher_routes = [
            ('/teacher/dashboard', 'GET'),
            ('/teacher/students', 'GET'),
            ('/teacher/subjects', 'GET'),
            (f'/teacher/subjects/{subject_id}/attendance', 'GET'),
            ('/attendance/scanner', 'GET'),
            ('/attendance/calendar', 'GET'),
        ]

        for path, method in teacher_routes:
            try:
                resp = client.open(path, method=method)
                if resp.status_code == 500:
                    errors.append((path, method, 'Teacher', resp.status_code, resp.data[:500].decode('utf-8', errors='replace')))
                    print(f"❌ 500 ERROR: [Teacher] {method} {path}")
                else:
                    print(f"✅ {resp.status_code}: [Teacher] {method} {path}")
            except Exception as e:
                errors.append((path, method, 'Teacher', 'EXCEPTION', str(e)))
                print(f"🔥 EXCEPTION: [Teacher] {method} {path} -> {e}")

        client.get('/auth/logout')

        # ==========================================
        # 3. STUDENT ROUTES AUDIT
        # ==========================================
        client.post('/auth/login', data={'identity': 'student', 'password': 'Student@1234'})
        student_routes = [
            ('/student/dashboard', 'GET'),
            ('/student/history', 'GET'),
            ('/student/id-card', 'GET'),
            ('/student/profile', 'GET'),
            ('/student/qr-code', 'GET'),
            ('/student/subjects', 'GET'),
            (f'/student/subjects/{subject_id}', 'GET'),
        ]

        for path, method in student_routes:
            try:
                resp = client.open(path, method=method)
                if resp.status_code == 500:
                    errors.append((path, method, 'Student', resp.status_code, resp.data[:500].decode('utf-8', errors='replace')))
                    print(f"❌ 500 ERROR: [Student] {method} {path}")
                else:
                    print(f"✅ {resp.status_code}: [Student] {method} {path}")
            except Exception as e:
                errors.append((path, method, 'Student', 'EXCEPTION', str(e)))
                print(f"🔥 EXCEPTION: [Student] {method} {path} -> {e}")

        client.get('/auth/logout')

        # ==========================================
        # 4. API ROUTES AUDIT (with Auth token)
        # ==========================================
        with app.app_context():
            token_t = teacher_user.generate_auth_token() if teacher_user else ''
            token_s = student_user.generate_auth_token() if student_user else ''

        headers_teacher = {'Authorization': f'Bearer {token_t}'}
        headers_student = {'Authorization': f'Bearer {token_s}'}

        api_routes = [
            ('/api/health', 'GET', {}),
            ('/api/dashboard/stats', 'GET', headers_teacher),
            ('/api/teacher/subjects', 'GET', headers_teacher),
            ('/api/student/me', 'GET', headers_student),
            ('/api/student/profile', 'GET', headers_student),
            ('/api/student/attendance', 'GET', headers_student),
            (f'/api/student/attendance/{subject_id}', 'GET', headers_student),
            ('/api/subjects', 'GET', headers_teacher),
            ('/api/attendance/today', 'GET', headers_teacher),
        ]

        for path, method, hdrs in api_routes:
            try:
                resp = client.open(path, method=method, headers=hdrs)
                if resp.status_code == 500:
                    errors.append((path, method, 'API', resp.status_code, resp.data[:500].decode('utf-8', errors='replace')))
                    print(f"❌ 500 ERROR: [API] {method} {path}")
                else:
                    print(f"✅ {resp.status_code}: [API] {method} {path}")
            except Exception as e:
                errors.append((path, method, 'API', 'EXCEPTION', str(e)))
                print(f"🔥 EXCEPTION: [API] {method} {path} -> {e}")

    print("\n" + "="*50)
    print(f"AUDIT SUMMARY: Total Errors Found = {len(errors)}")
    for err in errors:
        print(err)
    print("="*50)
    return len(errors)

if __name__ == '__main__':
    err_count = audit()
    sys.exit(err_count)
