# 🚀 Apex QR Attendance ERP System — Version 2.0

An enterprise-grade, full-stack **QR Attendance ERP System** built with **Python Flask**, **SQLAlchemy**, **ReportLab**, **openpyxl**, **Chart.js**, and modern **Glassmorphism Dark/Light UI**.

---

## 🌟 Key Highlights & Capabilities

* **Mobile Android APK App**: Native Flutter Android app ([`Apex_QR_Attendance_ERP_v2.0.apk`](file:///Users/anaypatel/QR%20Attendance%20ERP/Apex_QR_Attendance_ERP_v2.0.apk)) with camera QR scanning, real-time feedback, digital student identity cards, and configurable backend server sync.
* **Role-Based Access Control (RBAC)**: Secure multi-tier authentication (`Admin`, `Teacher`, `Student`) with password hashing via `werkzeug.security` and `@role_required` decorators.
* **Smart QR Attendance State Machine**:
  * **First Scan**: Marks **Time In** (Status: `Present`).
  * **Second Scan**: Marks **Time Out** (Computes duration attended).
  * **Subsequent Scans**: Duplicate prevention with friendly warning and 0% data corruption risk.
* **Live Camera QR Scanner**: Integrated webcam and mobile rear/front camera scanner powered by `html5-qrcode` with laser animation and synthesized Web Audio chimes (success chime and warning beep).
* **Multi-Format Export Engine**:
  * **Excel (`.xlsx`)**: Styled spreadsheets with headers, zebra striping, and summary statistics via `openpyxl`.
  * **PDF Reports**: Two-pass publication-grade landscape PDF reports with `Page X of Y` numbering via `ReportLab`.
  * **Digital Student ID Card**: High-resolution vector CR80 PDF ID cards with embedded cryptographic QR codes and student details.
  * **CSV & Print**: RFC 4180 standard CSV exports and print-optimized views.
* **Modern Design System**: Custom glassmorphism UI with HSL CSS design tokens, dynamic dark/light mode toggle with zero Flash-Of-Unstyled-Content (FOUC), and responsive sidebar navigation.
* **Interactive Analytics & Calendars**: Real-time KPI counters, Chart.js trend graphs, and an interactive 7-column monthly calendar with custom holiday markers.
* **RESTful JSON API**: Protected endpoints for mobile attendance scanners, dashboard statistics, and student lookup.
* **Enterprise Audit Trail**: Automated logging of all logins, attendance overrides, and administrative actions.
* **Turnkey Deployment Ready**: Production `Dockerfile`, `docker-compose.yml` (PostgreSQL 16), `render.yaml`, `railway.json`, and `Procfile`.

---

## 🛠 Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend** | Python 3.13, Flask, Blueprints, Flask-SQLAlchemy, Flask-Login, Flask-Migrate, Flask-WTF |
| **Database** | SQLite (development/testing) & PostgreSQL 16 (production) |
| **Frontend** | HTML5, CSS3 Glassmorphism tokens, Bootstrap 5.3, Bootstrap Icons, Chart.js, html5-qrcode |
| **Document Engines** | ReportLab (Vector PDF & ID cards), openpyxl (Excel), Pillow & qrcode (cryptographic QR) |
| **Deployment** | Gunicorn WSGI, Docker, Docker Compose, Render, Railway, Heroku |

---

## 🚀 Quick Start Guide

### 1. Prerequisites
* Python 3.10+ (Python 3.13 tested)
* `git`, `pip`, and `virtualenv`

### 2. Installation
```bash
# Clone the repository
git clone <repo-url>
cd "QR Attendance ERP"

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Database Initialization & Seeding
```bash
# Initialize SQLite database and run migrations
python run.py init-db

# Seed database with sample departments, courses, students, and demo accounts
python run.py seed
```

### 4. Running the Development Server
```bash
python run.py
```
> The application will start at **`http://127.0.0.1:5001`** (port 5001 is used to avoid macOS AirPlay Receiver port 5000 conflicts).

---

## 🔑 Demo Login Credentials

The database seeder provisions demo accounts for all roles:

| Role | Username / Identity | Password | Accessible Portals & Features |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `Admin@1234` | Full access: Student/Teacher CRUD, Settings, Audit Logs, QR Batch Gen, Reports, Scanner |
| **Teacher** | `teacher` | `Teacher@1234` | Teacher portal, department student rosters, QR camera scanner, manual attendance logs |
| **Student** | `student` | `Student@1234` | Student portal, profile, personal QR code, digital ID card PDF, attendance history |

---

## 📂 Project Architecture

```
QR Attendance ERP/
├── app/
│   ├── __init__.py            # Flask Application Factory
│   ├── config.py              # Dev, Test, Prod Configuration classes
│   ├── extensions.py          # SQLAlchemy, LoginManager, Migrate, CSRF
│   ├── models/                # Modular SQLAlchemy models
│   │   ├── user.py            # User credentials, roles (Admin/Teacher/Student)
│   │   ├── department.py      # Academic departments & courses
│   │   ├── student.py         # Student records, enrollment, attendance metrics
│   │   ├── teacher.py         # Faculty profiles & department assignments
│   │   ├── attendance.py      # Attendance records (Time In, Time Out, Method)
│   │   ├── holiday.py         # Institutional holiday schedule
│   │   ├── session.py         # Academic sessions/years
│   │   ├── settings.py        # System configuration key-values
│   │   └── audit.py           # Audit logging model
│   ├── admin/                 # Admin Blueprint (CRUD, Settings, Batch QR)
│   ├── attendance/            # Attendance Blueprint (Scanner, Manual, Calendar)
│   ├── reports/               # Reports Blueprint (Excel, PDF, CSV, Print, Email)
│   ├── student/               # Student Portal Blueprint (Profile, QR, ID Card)
│   ├── teacher/               # Teacher Portal Blueprint (Classes, Rosters)
│   ├── auth/                  # Authentication Blueprint (Login, Logout, Password)
│   ├── api/                   # RESTful JSON API Blueprint
│   ├── utils/                 # Utilities (QR generator, ID card PDF, decorators, mailer)
│   ├── static/                # CSS design system, JS chimes/theme switcher, uploads
│   └── templates/             # Jinja2 HTML templates with modern glassmorphism
├── tests/                     # Comprehensive automated pytest test suite (26 tests)
├── migrations/                # Flask-Migrate database migration scripts
├── Dockerfile                 # Production multi-stage Docker container
├── docker-compose.yml         # Web + PostgreSQL 16 container orchestrator
├── Procfile                   # Gunicorn WSGI process configuration
├── render.yaml                # Render deployment blueprint
├── railway.json               # Railway deployment configuration
├── requirements.txt           # Python package requirements
├── run.py                     # Application runner & CLI management commands
└── pytest.ini                 # Pytest runner configuration
```

---

## 🧪 Automated Testing Suite

The system includes comprehensive automated tests covering all modules:
```bash
# Run the complete test suite
pytest tests/ -v
```

### Test Coverage Highlights
* `tests/test_setup.py`: App creation, database connectivity, and root redirects.
* `tests/test_auth.py`: Password hashing, session lifecycle, RBAC enforcement.
* `tests/test_students.py`: Student CRUD, roll number validation, photo handling.
* `tests/test_teachers.py`: Faculty registration, department mapping, status toggling.
* `tests/test_attendance.py`: QR lifecycle (Time In ➔ Time Out ➔ Duplicate prevention ➔ Manual override).
* `tests/test_reports.py`: Excel (`.xlsx`), PDF, CSV, and Print export generation.
* `tests/test_student_portal.py`: Student self-service, ID card PDF download, QR generation.
* `tests/test_teacher_portal.py`: Teacher dashboard and department rosters.
* `tests/test_api.py`: JSON API endpoints for attendance scanning, health, and statistics.

---

## 📡 RESTful JSON API Reference

### 1. Mark Attendance Scan
* **URL**: `POST /api/attendance/scan`
* **Auth**: Teacher or Admin session required
* **Payload**: `{"token": "<student_qr_token>"}`
* **Response (Time In)**:
```json
{
  "success": true,
  "action": "TIME_IN",
  "message": "Time In marked successfully at 09:15 AM.",
  "student": {
    "student_id": "STU2026001",
    "full_name": "Aarav Sharma",
    "department_code": "CSE"
  },
  "attendance": {
    "time_in": "09:15 AM",
    "status": "Present"
  }
}
```

### 2. Live Dashboard KPI Counters
* **URL**: `GET /api/dashboard/stats`
* **Response**:
```json
{
  "success": true,
  "total_students": 120,
  "total_teachers": 14,
  "present_today": 112,
  "absent_today": 8,
  "attendance_rate": 93.3
}
```

---

## 🚢 Docker & Production Deployment

### Run with Docker Compose
```bash
# Launch Web and PostgreSQL containers
docker-compose up -d --build

# View logs
docker-compose logs -f
```
Access the application at `http://localhost:5001`.

---

## 🆓 ZERO-COST LIVE DEPLOYMENT GUIDE (Render + PostgreSQL)

Follow this complete step-by-step procedure to deploy the entire ERP system live on the web with free automatic HTTPS, PostgreSQL database, and zero hosting costs.

```
LOCAL DEVELOPMENT ➔ GITHUB REPOSITORY ➔ RENDER (WEB + POSTGRESQL) ➔ LIVE HTTPS ERP
```

### Step 1: Create a GitHub Repository
1. Log in to [GitHub](https://github.com/) and click **New Repository**.
2. Name the repository: `qr-attendance-erp`.
3. Set the visibility to **Public** or **Private**, and leave "Initialize with README" unchecked.

### Step 2: Push Project to GitHub
In your local terminal inside the project directory:
```bash
git init
git add .
git commit -m "Initial commit: QR Attendance ERP V2.0 with production deployment config"
git branch -M main
git remote add origin https://github.com/<YOUR_USERNAME>/qr-attendance-erp.git
git push -u origin main
```

### Step 3: Create a Free PostgreSQL Database on Render
1. Sign up or log in to [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** ➔ **PostgreSQL**.
3. Fill in the database details:
   * **Name**: `qr-attendance-db`
   * **Database**: `qr_attendance_db`
   * **User**: `qr_user`
   * **Region**: Choose the region closest to you (e.g. *Oregon (US West)* or *Frankfurt (EU)*).
   * **Instance Type**: Select **Free**.
4. Click **Create Database**.
5. Once created, copy the **Internal Database URL** (if deploying both web and DB in the same Render region) or the **External Database URL**.

### Step 4: Create Render Web Service
1. In the Render Dashboard, click **New +** ➔ **Web Service**.
2. Select **Build and deploy from a Git repository**.
3. Connect your GitHub account and select your `qr-attendance-erp` repository.

### Step 5: Configure Build & Start Settings
* **Name**: `apex-qr-erp` (or any unique name of your choice)
* **Region**: Same region as your database (e.g. *Oregon*)
* **Branch**: `main`
* **Root Directory**: Leave blank (root of repository)
* **Runtime**: `Python 3`
* **Build Command**:
  ```bash
  pip install --upgrade pip && pip install -r requirements.txt && python run.py init-db && python run.py seed
  ```
* **Start Command**:
  ```bash
  gunicorn run:app --workers 4 --bind 0.0.0.0:$PORT --access-logfile - --error-logfile -
  ```
* **Instance Type**: Select **Free**.

### Step 6: Configure Environment Variables
Under the **Environment Variables** section in Render, add the following key-value pairs:

| Variable Name | Value / Notes |
| :--- | :--- |
| `PYTHON_VERSION` | `3.13.0` |
| `FLASK_ENV` | `production` |
| `SECRET_KEY` | Click **Generate** on Render or paste a 32+ character random string |
| `DATABASE_URL` | Paste your PostgreSQL connection URL from Step 3 (or link directly via Render Blueprint) |
| `INSTITUTION_NAME` | `Apex Institute of Technology & Management` |
| `INSTITUTION_EMAIL` | `contact@apex-institute.edu` |
| `INSTITUTION_PHONE` | `+1-555-0199` |
| `UPLOAD_FOLDER` | `app/static/uploads` |

*(Optional SMTP variables: `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD` can be added if automated email report dispatch is desired).*

### Step 7: Deploy the Service
Click **Create Web Service**.
Render will automatically clone the repository, install dependencies, run migrations, seed demo accounts, and launch Gunicorn.

### Step 8: Open the Live HTTPS URL
Once the deployment status shows **Live**, open your free Render subdomain:
👉 **`https://apex-qr-erp.onrender.com`** *(or your chosen name)*

### Step 9: Verify Live Features & Camera Permission
* Navigate to `https://<your-app>.onrender.com/auth/login`.
* Sign in using the provisioned credentials:
  * **Identity**: `admin` &nbsp;|&nbsp; **Password**: `Admin@1234`
  * Or **Teacher**: `teacher` &nbsp;|&nbsp; `Teacher@1234`
  * Or **Student**: `student` &nbsp;|&nbsp; `Student@1234`
* Go to **QR Scanner** (`/attendance/scanner`).
* The browser or phone will prompt for camera access. Because the site is served over **secure HTTPS**, camera permissions work natively without localhost workarounds!
* Point the camera at any student QR code (or student ID card) to test live **Time In** and **Time Out** verification.

---

## ⚠️ FREE-TIER LIMITATIONS & MITIGATIONS

When running on free-tier hosting infrastructure, keep in mind the following constraints:

1. **Cold Starts / Inactivity Sleep**:
   * *Limitation*: Render Free Web Services spin down to save compute resources after 15 minutes of inactivity.
   * *Behavior*: The first request after sleep will take approximately **30 to 50 seconds** to wake up the server. Subsequent requests are instant.
   * *Mitigation*: For important events or demo presentations, keep the server awake using a free uptime monitor (e.g. UptimeRobot or Cron-Job.org pinging `/api/health` every 10 minutes).

2. **Database Retention Limits**:
   * *Limitation*: Render Free PostgreSQL databases remain active for 30 days.
   * *Mitigation*: If you require perpetual free database hosting, create a free database at [Neon.tech](https://neon.tech/) (0.5 GB perpetual free serverless Postgres) or [Supabase](https://supabase.com/) and paste the connection string into `DATABASE_URL` in Render.

3. **Ephemeral File System (Uploads)**:
   * *Limitation*: Free containers reset their local file system on restart or re-deploy. Student photos uploaded to `app/static/uploads` will be wiped during a redeployment.
   * *Mitigation*: For perpetual photo storage in production, student avatar URLs can be pointed to free cloud image hosts (like Cloudinary or Supabase Storage).

4. **Bandwidth & Build Minutes**:
   * *Limitation*: Render provides 100 GB of outbound bandwidth and 500 build minutes per month on the free tier, which is more than sufficient for thousands of attendance scans.

5. **Email Sending Limits**:
   * *Limitation*: Free Gmail SMTP limits you to 100–500 emails/day; Brevo free tier provides 300 emails/day.

---

## 📄 License
This project is licensed under the MIT License.

