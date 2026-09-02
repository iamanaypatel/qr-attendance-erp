from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SelectField, DateField, TextAreaField, BooleanField, SubmitField, PasswordField
from wtforms.validators import DataRequired, Email, Length, Optional

class StudentForm(FlaskForm):
    student_id = StringField('Student ID', validators=[DataRequired(), Length(max=32)])
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=120)])
    father_name = StringField("Father's Name", validators=[Optional(), Length(max=120)])
    mother_name = StringField("Mother's Name", validators=[Optional(), Length(max=120)])
    email = StringField('Email Address', validators=[DataRequired(), Email(check_deliverability=False), Length(max=120)])
    phone = StringField('Phone Number', validators=[Optional(), Length(max=20)])
    date_of_birth = DateField('Date of Birth', validators=[Optional()], format='%Y-%m-%d')
    gender = SelectField('Gender', choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')])
    department_id = SelectField('Department', coerce=int, validators=[DataRequired()])
    course = StringField('Course / Degree', validators=[DataRequired(), Length(max=100)])
    semester = SelectField('Semester', choices=[
        ('1st', '1st Semester'), ('2nd', '2nd Semester'),
        ('3rd', '3rd Semester'), ('4th', '4th Semester'),
        ('5th', '5th Semester'), ('6th', '6th Semester'),
        ('7th', '7th Semester'), ('8th', '8th Semester')
    ])
    section = StringField('Section', validators=[Optional(), Length(max=10)])
    roll_number = StringField('Roll Number', validators=[DataRequired(), Length(max=50)])
    address = TextAreaField('Permanent Address', validators=[Optional()])
    photo = FileField('Student Photo', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png', 'webp'], 'Images only (.jpg, .png, .webp)')])
    create_user_account = BooleanField('Create Portal Login for Student (Default Password: Student@1234)', default=True)
    submit = SubmitField('Save Student')

class TeacherForm(FlaskForm):
    employee_id = StringField('Employee ID', validators=[DataRequired(), Length(max=32)])
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=120)])
    email = StringField('Email Address', validators=[DataRequired(), Email(check_deliverability=False), Length(max=120)])
    phone = StringField('Phone Number', validators=[Optional(), Length(max=20)])
    department_id = SelectField('Department', coerce=int, validators=[DataRequired()])
    designation = StringField('Designation', validators=[DataRequired(), Length(max=100)], default='Assistant Professor')
    is_active = BooleanField('Account Active', default=True)
    password = PasswordField('Login Password (Leave empty for default: Teacher@1234)', validators=[Optional(), Length(min=6)])
    submit = SubmitField('Save Teacher')

class DepartmentForm(FlaskForm):
    name = StringField('Department Name', validators=[DataRequired(), Length(max=100)])
    code = StringField('Department Code', validators=[DataRequired(), Length(max=20)])
    description = TextAreaField('Description', validators=[Optional()])
    submit = SubmitField('Save Department')

class HolidayForm(FlaskForm):
    title = StringField('Holiday Title', validators=[DataRequired(), Length(max=120)])
    date = DateField('Holiday Date', validators=[DataRequired()], format='%Y-%m-%d')
    description = TextAreaField('Description', validators=[Optional()])
    submit = SubmitField('Save Holiday')

class AcademicSessionForm(FlaskForm):
    name = StringField('Session Name (e.g. 2025-2026)', validators=[DataRequired(), Length(max=50)])
    start_date = DateField('Start Date', validators=[DataRequired()], format='%Y-%m-%d')
    end_date = DateField('End Date', validators=[DataRequired()], format='%Y-%m-%d')
    is_active = BooleanField('Set as Active Session', default=False)
    submit = SubmitField('Save Session')

class SystemSettingsForm(FlaskForm):
    institution_name = StringField('Institution Name', validators=[DataRequired(), Length(max=150)])
    institution_email = StringField('Institution Email', validators=[DataRequired(), Email()])
    institution_phone = StringField('Contact Phone', validators=[DataRequired()])
    institution_address = TextAreaField('Campus Address', validators=[DataRequired()])
    attendance_start_time = StringField('Attendance Check-In Start (HH:MM)', validators=[DataRequired()])
    attendance_end_time = StringField('Attendance Check-Out End (HH:MM)', validators=[DataRequired()])
    duplicate_scan_cooldown_seconds = StringField('Duplicate Scan Cooldown (seconds)', validators=[DataRequired()])
    submit = SubmitField('Save Settings')
