from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

# Login manager configuration
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this system.'
login_manager.login_message_category = 'warning'
login_manager.session_protection = 'basic'
