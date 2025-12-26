def get_scheduler_service():
    pass

def init_scheduler():
    pass

def shutdown_scheduler():
    pass

# OOP tabanlı Flask App Factory
import logging
import os
import sys
from datetime import date, datetime, time
from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_mail import Mail
from flask_moment import Moment
from flask_wtf.csrf import CSRFProtect

class AppFactory:
    def _register_jinja_globals(self, app):
        def get_status_badge_class(status):
            if status == "approved":
                return "bg-success text-white"
            elif status == "pending":
                return "bg-warning text-dark"
            elif status == "rejected":
                return "bg-danger text-white"
            return "bg-secondary text-white"
        def get_status_text(status):
            if status == "approved":
                return "Onaylandı"
            elif status == "pending":
                return "Beklemede"
            elif status == "rejected":
                return "Reddedildi"
            return "Bilinmiyor"
        app.jinja_env.globals.update(get_status_badge_class=get_status_badge_class)
        app.jinja_env.globals.update(get_status_text=get_status_text)
    def __init__(self):
        self.app = None
        self.mail = None
        self.moment = None
        self.csrf = None
        self._configure_logging()
        self._set_utf8_encoding()
        load_dotenv()

    def _configure_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )

    def _set_utf8_encoding(self):
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')

    def create_app(self):
        app = Flask(__name__)
        self._configure_app(app)
        self.mail = Mail(app)
        self.moment = Moment(app)
        self.csrf = CSRFProtect(app)
        self._register_blueprints(app)
        self._register_context_processors(app)
        self._register_error_handlers(app)
        self._register_before_request(app)
        self._register_jinja_globals(app)
        self.app = app
        return app

    def _configure_app(self, app):
        app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
        # SQLAlchemy config removed. Only Firebase is used.
        app.config['JSON_AS_ASCII'] = False
        app.config['SESSION_COOKIE_SECURE'] = False
        app.config['SESSION_COOKIE_HTTPONLY'] = True
        app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
        app.config['PERMANENT_SESSION_LIFETIME'] = 30 * 24 * 3600
        app.config['WTF_CSRF_TIME_LIMIT'] = None
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
        app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
        app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
        app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
        app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
        app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', os.getenv('MAIL_USERNAME'))

    def _register_blueprints(self, app):
        from routes import admin_bp, appointments_bp, auth_bp, dashboard_bp
        app.register_blueprint(auth_bp, url_prefix='/auth')
        app.register_blueprint(appointments_bp, url_prefix='/appointments')
        app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
        app.register_blueprint(admin_bp, url_prefix='/admin')

    def _register_context_processors(self, app):
        @app.context_processor
        def inject_user():
            from flask_wtf.csrf import generate_csrf
            context = {'csrf_token': generate_csrf}
            if session.get('user_id'):
                from firebase_realtime import get_data
                users = get_data('users') or {}
                current_user = users.get(str(session.get('user_id')))
                context['current_user'] = current_user
            else:
                context['current_user'] = None
            return context

    def _register_error_handlers(self, app):
        @app.errorhandler(404)
        def not_found_error(error):
            return render_template('errors/404.html'), 404

        @app.errorhandler(500)
        def internal_error(error):
            return render_template('errors/500.html'), 500

    def _register_before_request(self, app):
        @app.before_request
        def check_single_session():
            if session.get('user_id'):
                try:
                    from firebase_realtime import get_data
                    users = get_data('users') or {}
                    user = users.get(str(session.get('user_id')))
                    if user:
                        token_in_db = user.get('session_token')
                        token_in_session = session.get('session_token')
                        if token_in_session and token_in_db and token_in_session != token_in_db:
                            session.pop('user_id', None)
                            session.pop('session_token', None)
                            flash('Başka bir oturum açıldığı için çıkış yapıldı.', 'warning')
                            return redirect(url_for('auth.login'))
                    else:
                        session.pop('user_id', None)
                        session.pop('session_token', None)
                except Exception as e:
                    app.logger.error(f"Session check error: {str(e)}")

    # Route methods
    def add_routes(self):
        app = self.app

        @app.route('/')
        def index():
            if session.get('user_id'):
                return redirect(url_for('dashboard.dashboard'))
            return render_template('index.html')

        @app.route('/about')
        def about():
            return render_template('about.html')
        @app.route('/kvkk')
        def kvkk():
            return render_template('kvkk.html')

    # Scheduler ve diğer servisler için placeholder metotlar
    def get_scheduler_service(self):
        pass
    def init_scheduler(self):
        pass
    def shutdown_scheduler(self):
        pass
factory = AppFactory()
app = factory.create_app()
factory.add_routes()

if __name__ == '__main__':
    
    app.run(debug=True, host='0.0.0.0', port=5000)
