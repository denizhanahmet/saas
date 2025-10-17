# Flask-Mail uzantısını blueprint importlarından önce ekle
# Flask-Mail uzantısını blueprint importlarından önce ekle
from flask_mail import Mail
# Flask-Migrate entegrasyonu
from flask_migrate import Migrate
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_moment import Moment
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, time
import os
import logging
from dotenv import load_dotenv

# Environment variables
load_dotenv()

# Configure logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Set UTF-8 encoding for console output
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///appointments.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JSON_AS_ASCII'] = False  # Enable UTF-8 in JSON responses
# Mail config
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', os.getenv('MAIL_USERNAME'))
mail = Mail(app)

# Flask-Moment entegrasyonu
moment = Moment(app)

# Initialize extensions
from models import db, User, Appointment, BlockedDay, Client, SmsLog
db.init_app(app)
migrate = Migrate(app, db)
csrf = CSRFProtect(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Bu sayfaya erişmek için giriş yapmalısınız.'
login_manager.login_message_category = 'info'

# Initialize scheduler service
from services.scheduler_service import SchedulerService
scheduler_service = None

def get_scheduler_service():
    """Get the scheduler service instance"""
    return scheduler_service

# Import routes after models are initialized
from routes import auth_bp, appointments_bp, dashboard_bp, admin_bp

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(appointments_bp, url_prefix='/appointments')
app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
app.register_blueprint(admin_bp, url_prefix='/admin')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

def init_scheduler():
    """Initialize and start the scheduler service"""
    global scheduler_service
    try:
        scheduler_service = SchedulerService(db, app)
        scheduler_service.start()
        
        # Schedule all pending reminders
        with app.app_context():
            scheduler_service.schedule_all_pending_reminders()
        
        app.logger.info("Scheduler service initialized and started")
    except Exception as e:
        app.logger.error(f"Failed to initialize scheduler: {str(e)}")

def shutdown_scheduler():
    """Stop the scheduler service"""
    global scheduler_service
    if scheduler_service:
        try:
            scheduler_service.stop()
            app.logger.info("Scheduler service stopped")
        except Exception as e:
            app.logger.error(f"Failed to stop scheduler: {str(e)}")



from flask import session

@app.before_request
def check_single_session():
    if current_user.is_authenticated:
        from models import User
        user_db = User.query.get(current_user.id)
        token_in_db = user_db.session_token if user_db else None
        token_in_session = session.get('session_token')
        # Her istekte session_token'ı güncelle
        if token_in_db:
            session['session_token'] = token_in_db
        if token_in_session and token_in_db and token_in_session != token_in_db:
            logout_user()
            session.pop('session_token', None)
            flash('Başka bir oturum açıldığı için çıkış yapıldı.', 'warning')
            return redirect(url_for('auth.login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Initialize scheduler
        init_scheduler()
    try:
        app.run(debug=True, host='0.0.0.0', port=5000)
    finally:
        # Cleanup scheduler on shutdown
        shutdown_scheduler()
