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
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

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
        def get_user_work_hours(user_id):
            from firebase_realtime import get_data
            user = get_data(f'users/{user_id}')
            if user:
                return {
                    'start': user.get('work_start_time', '09:00'),
                    'end': user.get('work_end_time', '17:00')
                }
            return {'start': '09:00', 'end': '17:00'}
        app.jinja_env.globals.update(get_status_badge_class=get_status_badge_class)
        app.jinja_env.globals.update(get_status_text=get_status_text)
        app.jinja_env.globals.update(get_user_work_hours=get_user_work_hours)
    def __init__(self):
        self.app = None
        self.mail = None
        self.moment = None
        self.csrf = None
        self.scheduler_service = None
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
        
        # Rate Limiter - Brute force saldırılarına karşı koruma
        # NOT: Limitler normal kullanımı engellemeyecek şekilde ayarlandı
        self.limiter = Limiter(
            key_func=get_remote_address,
            app=app,
            default_limits=["1000 per day", "200 per hour"],  # Daha makul limitler
            storage_uri="memory://",
            strategy="fixed-window"
        )
        # Limiter'ı global olarak erişilebilir yap
        app.limiter = self.limiter
        
        self._register_blueprints(app)
        
        # iyzico dış callback'leri için CSRF kontrolünü atla
        @app.before_request
        def skip_csrf_for_iyzico():
            if request.path in ['/subscription/callback', '/subscription/webhook']:
                # iyzico endpoint'leri için CSRF doğrulamasını atla
                from flask import g
                g.csrf_valid = True
        
        # iyzico route'larını CSRF'den muaf tut
        from routes.subscription import callback
        self.csrf.exempt(callback)
        
        self._register_context_processors(app)
        self._register_error_handlers(app)
        self._register_before_request(app)
        self._register_jinja_globals(app)
        self.app = app
        return app

    def _configure_app(self, app):
        # SECRET_KEY güvenlik kontrolü - zorunlu ve güvenli olmalı
        secret_key = os.getenv('SECRET_KEY')
        if not secret_key or secret_key == 'your-secret-key-here':
            if os.getenv('FLASK_ENV') == 'production':
                raise ValueError("CRITICAL: SECRET_KEY must be set to a secure random value in production!")
            else:
                # Geliştirme ortamı için uyarı ver ama devam et
                import secrets
                secret_key = secrets.token_hex(32)
                logging.warning("WARNING: SECRET_KEY not set! Using temporary key. Set SECRET_KEY in .env for production.")
        app.config['SECRET_KEY'] = secret_key
        # SQLAlchemy konfigürasyonu kaldırıldı. Sadece Firebase kullanılıyor.
        app.config['JSON_AS_ASCII'] = False
        app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB max request size
        
        # Session Cookie Güvenlik Ayarları
        # Üretim ortamında HTTPS zorunlu, geliştirmede HTTP kabul edilir
        is_production = os.getenv('FLASK_ENV') == 'production'
        app.config['SESSION_COOKIE_SECURE'] = is_production  # Üretimde sadece HTTPS
        app.config['SESSION_COOKIE_HTTPONLY'] = True  # JavaScript erişimini engelle
        app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF koruması
        app.config['PERMANENT_SESSION_LIFETIME'] = 30 * 24 * 3600
        
        # CSRF Koruması - AKTİF
        app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 saat token geçerliliği
        app.config['WTF_CSRF_ENABLED'] = True  # CSRF koruması aktif
        app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
        app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
        app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
        app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
        app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
        app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', os.getenv('MAIL_USERNAME'))

    def _register_blueprints(self, app):
        from routes import (admin_bp, appointments_bp, auth_bp, dashboard_bp, 
                            exports_bp, scheduling_bp, waitlist_bp, subscription_bp)
        app.register_blueprint(auth_bp, url_prefix='/auth')
        app.register_blueprint(appointments_bp, url_prefix='/appointments')
        app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
        app.register_blueprint(admin_bp, url_prefix='/admin')
        app.register_blueprint(exports_bp, url_prefix='/export')
        app.register_blueprint(scheduling_bp, url_prefix='/api')
        app.register_blueprint(waitlist_bp, url_prefix='/waitlist')
        app.register_blueprint(subscription_bp, url_prefix='/subscription')

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
            # Hata detaylarını logla ama kullanıcıya gösterme
            app.logger.error(f"500 hatası: {str(error)}")
            return render_template('errors/500.html'), 500

        @app.errorhandler(413)
        def request_entity_too_large(error):
            return render_template('errors/413.html'), 413
        
        # Güvenlik Başlıkları - Yaygın web saldırılarına karşı koruma
        @app.after_request
        def add_security_headers(response):
            # Clickjacking koruması - sayfanın iframe'de yüklenmesini engelle
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            # MIME type sniffing koruması
            response.headers['X-Content-Type-Options'] = 'nosniff'
            # XSS koruması (modern tarayıcılarda CSP tercih edilir)
            response.headers['X-XSS-Protection'] = '1; mode=block'
            # Referrer bilgisi sızıntısını azalt
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            # Content Security Policy — XSS saldırılarını engelle
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.tailwindcss.com https://npmcdn.com https://*.iyzipay.com https://*.iyzico.com; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.tailwindcss.com https://*.iyzipay.com https://*.iyzico.com; "
                "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com https://*.iyzipay.com; "
                "img-src 'self' data: blob: https://*.iyzipay.com https://*.iyzico.com https://www.iyzico.com; "
                "connect-src 'self' https://cdn.tailwindcss.com https://*.iyzipay.com https://*.iyzico.com; "
                "frame-src 'self' https://*.iyzipay.com https://*.iyzico.com"
            )
            # Cache kontrolü - hassas sayfalarda önbellek devre dışı
            if request.path.startswith('/admin') or request.path.startswith('/dashboard'):
                response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                response.headers['Pragma'] = 'no-cache'
            return response

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
        
        @app.before_request
        def check_subscription():
            """Korumalı route'lar için kullanıcının aktif aboneliği veya trial süresi olup olmadığını kontrol et"""
            # Statik dosyalar için atla
            if request.path.startswith('/static'):
                return
            
            # Abonelik gerektirmeyen yollar (herkese açık route'lar)
            allowed_paths = [
                '/auth/', '/subscription/', '/about', '/waitlist/public',
                '/waitlist/success', '/appointments/book/', '/appointments/cancel/',
                '/waitlist/claim/', '/kvkk'
            ]
            
            # Tam ana yola izin ver
            if request.path == '/':
                return
            
            # Yolun izin verilen listede olup olmadığını kontrol et
            for allowed in allowed_paths:
                if request.path.startswith(allowed):
                    return
            
            # Diğer tüm yollar için kullanıcı giriş yapmış ve aktif aboneliği olmalı
            if not session.get('user_id'):
                # Giriş yapılmamış - login_required dekoratörlerinin işlemesine izin ver
                return
            
            # Kullanıcı giriş yapmış - superadmin mi kontrol et (abonelik kontrolünü atla)
            from firebase_realtime import get_data
            user = get_data(f"users/{session['user_id']}")
            if user and user.get('is_superadmin'):
                # Superadmin kullanıcılarının aboneliğe ihtiyacı yok
                return
            
            # Trial veya abonelik kontrolü
            if user:
                subscription_status = user.get('subscription_status', '')
                
                # Aktif abonelik varsa geç
                if subscription_status == 'active':
                    return
                
                # Nested subscription objesinden de kontrol et (ödeme sonrası uyum)
                subscription_obj = user.get('subscription', {})
                if isinstance(subscription_obj, dict) and subscription_obj.get('status') == 'active':
                    expires_at = subscription_obj.get('expires_at')
                    if expires_at:
                        from datetime import datetime as dt_check
                        try:
                            exp = dt_check.fromisoformat(expires_at.replace('Z', '+00:00'))
                            if exp.tzinfo:
                                exp = exp.replace(tzinfo=None)
                            if dt_check.utcnow() < exp:
                                # Top-level alanı da senkronize et
                                from firebase_realtime import update_data as sync_update
                                sync_update(f"users/{session['user_id']}", {'subscription_status': 'active'})
                                return
                        except (ValueError, TypeError):
                            pass
                
                # Trial durumunu kontrol et
                if subscription_status == 'trial':
                    trial_ends_at = user.get('trial_ends_at')
                    if trial_ends_at:
                        from datetime import datetime
                        try:
                            trial_end = datetime.fromisoformat(trial_ends_at.replace('Z', '+00:00'))
                            # Timezone-naive karşılaştırma için
                            if trial_end.tzinfo:
                                trial_end = trial_end.replace(tzinfo=None)
                            
                            if datetime.utcnow() < trial_end:
                                # Trial hala geçerli
                                return
                        except (ValueError, TypeError):
                            pass
                    
                    # Trial süresi dolmuş - durumu güncelle
                    from firebase_realtime import update_data
                    update_data(f"users/{session['user_id']}", {'subscription_status': 'expired'})
            
            # Aktif abonelik veya geçerli trial yok - kilitle
            flash('Deneme süreniz doldu veya aktif aboneliğiniz yok. Devam etmek için lütfen bir plan seçin.', 'warning')
            return redirect(url_for('subscription.trial_expired'))

    # Route metodları
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

    # Scheduler Yönetimi
    def get_scheduler_service(self):
        return self.scheduler_service
        
    def init_scheduler(self):
        """Zamanlayıcı servisini başlat ve çalıştır"""
        if not self.scheduler_service and self.app:
            from services.scheduler_service import SchedulerService
            # Scheduler servisini başlat
            self.scheduler_service = SchedulerService(self.app)
            self.scheduler_service.start()
            # Bekleyen hatırlatmaları yükle
            self.scheduler_service.schedule_all_pending_reminders()
            
    def shutdown_scheduler(self):
        if self.scheduler_service:
            self.scheduler_service.stop()
            
factory = AppFactory()
app = factory.create_app()
factory.add_routes()

if __name__ == '__main__':
    # Development ortamında scheduler'ı başlat
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or os.name == 'nt':
        factory.init_scheduler()
    
    # GÜVENLİK: Production'da debug=False olmalı
    # FLASK_ENV=production veya FLASK_DEBUG=0 ayarla
    debug_mode = os.getenv('FLASK_DEBUG', '0') == '1' or os.getenv('FLASK_ENV') == 'development'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)
