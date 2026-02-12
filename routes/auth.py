import logging
import threading


def send_async_email(app, msg):
    with app.app_context():
        current_app.extensions['mail'].send(msg)
from datetime import datetime, timedelta

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, session, url_for)
# Flask-Login kaldırıldı, session tabanlı custom oturum yönetimi kullanıyoruz
from flask_mail import Message
from flask_wtf.csrf import generate_csrf
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint('auth', __name__)

# Open Redirect koruması
from urllib.parse import urlparse

def _is_safe_url(target):
    """Yönlendirme URL'inin güvenli (aynı host) olduğunu doğrular."""
    host_url = urlparse(request.host_url)
    test_url = urlparse(target)
    if test_url.scheme and test_url.scheme not in ('http', 'https'):
        return False
    if test_url.netloc and test_url.netloc != host_url.netloc:
        return False
    return True

# Rate limiter yardımcı fonksiyonu
def get_limiter():
    """Mevcut uygulama context'inden limiter'ı getir"""
    return current_app.limiter if hasattr(current_app, 'limiter') else None

def get_default_working_hours():
    """Varsayılan çalışma saatleri oluştur (Pzt-Cum 09:00-18:00)"""
    return {
        'monday': {'enabled': True, 'start': '09:00', 'end': '18:00'},
        'tuesday': {'enabled': True, 'start': '09:00', 'end': '18:00'},
        'wednesday': {'enabled': True, 'start': '09:00', 'end': '18:00'},
        'thursday': {'enabled': True, 'start': '09:00', 'end': '18:00'},
        'friday': {'enabled': True, 'start': '09:00', 'end': '18:00'},
        'saturday': {'enabled': False, 'start': '09:00', 'end': '13:00'},
        'sunday': {'enabled': False, 'start': '', 'end': ''}
    }

def parse_working_hours_from_form(form):
    """Form verilerinden çalışma saatlerini parse et"""
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    working_hours = {}
    for day in days:
        enabled = form.get(f'working_{day}') == 'on'
        start = form.get(f'working_{day}_start', '09:00')
        end = form.get(f'working_{day}_end', '18:00')
        working_hours[day] = {
            'enabled': enabled,
            'start': start if enabled else '',
            'end': end if enabled else ''
        }
    return working_hours

# --- Session Caching Helpers ---
# Hassas bilgiler (şifre hash, salt, token) cache'lenmez
SAFE_USER_FIELDS = [
    'id', 'email', 'first_name', 'last_name', 'phone', 'company_name',
    'unique_link', 'logo_path', 'created_at', 'is_active', 'is_superadmin',
    'role', 'sms_quota', 'remaining_sms_quota', 'working_hours'
]

def cache_user_to_session(user_data):
    """Kullanıcı bilgilerini session'a güvenli şekilde cache'le (hassas bilgiler hariç)"""
    if not user_data:
        return
    cached = {k: v for k, v in user_data.items() if k in SAFE_USER_FIELDS}
    cached['_cache_time'] = datetime.utcnow().isoformat()
    session['user_cache'] = cached

def get_cached_user(force_refresh=False):
    """Session'dan cache'lenmiş kullanıcı bilgilerini al, yoksa Firebase'den çek"""
    user_id = session.get('user_id')
    if not user_id:
        return None
    
    # Cache kontrolü
    if not force_refresh and 'user_cache' in session:
        cache = session['user_cache']
        # Cache 5 dakikadan eski mi kontrol et
        if cache.get('_cache_time'):
            try:
                cache_time = datetime.fromisoformat(cache['_cache_time'])
                if (datetime.utcnow() - cache_time).total_seconds() < 300:  # 5 dakika
                    return cache
            except:
                pass
    
    # Cache yok veya eski, Firebase'den çek
    from firebase_realtime import get_data
    users = get_data('users') or {}
    user = users.get(str(user_id))
    if user:
        cache_user_to_session(user)
        return session.get('user_cache')
    return None

def clear_user_cache():
    """Session cache'ini temizle"""
    session.pop('user_cache', None)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Session tabanlı oturum kontrolü
    session.permanent = True  # Session'ı kalıcı yap (CSRF için gerekli)
    
    if session.get('user_id'):
        return redirect(url_for('dashboard.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if not email or not password:
            flash('Email ve şifre gerekli!', 'error')
            return render_template('auth/login.html', csrf_token=generate_csrf)
        from firebase_realtime import get_data
        users = get_data('users') or {}
        user = next((u for u in users.values() if u.get('email') == email), None)
        if user and user.get('password_hash') and user.get('password_salt') and user.get('password_iterations'):
            from services.password_utils import verify_password_pbkdf2
            if verify_password_pbkdf2(password, user['password_hash'], user['password_salt'], int(user['password_iterations'])):
                if not user.get('is_active', True):
                    flash('Hesabınız deaktif edilmiş!', 'error')
                    return render_template('auth/login.html', csrf_token=generate_csrf)
                import secrets
                from firebase_realtime_transaction import atomic_update
                user['session_token'] = secrets.token_hex(32)
                user_id = user.get('id')
                if not user_id:
                    flash('Kullanıcı kaydında eksik id. Lütfen tekrar kayıt olun.', 'error')
                    return render_template('auth/login.html', csrf_token=generate_csrf)
                atomic_update(f"users/{user_id}", lambda current: user)
                session['session_token'] = user['session_token']
                session['user_id'] = user_id
                cache_user_to_session(user)  # Session cache
                # Log başarılı giriş
                from services.activity_logger import ActivityLogger
                ActivityLogger.log_activity(
                    user_id=user_id,
                    action=ActivityLogger.LOGIN_SUCCESS,
                    resource=ActivityLogger.RESOURCE_AUTH,
                    details='Kullanıcı girişi başarılı',
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string
                )
                
                # Zorunlu şifre değişikliği kontrolü
                if user.get('force_password_change'):
                    flash('Güvenliğiniz için şifrenizi değiştirmeniz gerekiyor.', 'warning')
                    return redirect(url_for('auth.force_change_password'))
                
                flash(f"Hoş geldiniz, {user.get('first_name','')} {user.get('last_name','')}!", 'success')
                next_page = request.args.get('next')
                if next_page and _is_safe_url(next_page):
                    return redirect(next_page)
                return redirect(url_for('dashboard.dashboard'))
            # Başarısız giriş denemesini logla - güvenlik izleme için
            logging.warning(f"Başarısız giriş denemesi: {email} - IP: {request.remote_addr}")
            from services.activity_logger import ActivityLogger
            ActivityLogger.log_activity(
                user_id='unknown',
                action=ActivityLogger.LOGIN_FAILED,
                resource=ActivityLogger.RESOURCE_AUTH,
                details='Şifre hatalı',
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string,
                success=False
            )
            flash('Geçersiz email veya şifre!', 'error')
            return render_template('auth/login.html', csrf_token=generate_csrf)
        elif user and user.get('password_hash'):
            import hashlib
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            if user.get('password_hash') == password_hash:
                user_id = user.get('id')
                if not user_id:
                    flash('Kullanıcı kaydında eksik id. Lütfen tekrar kayıt olun.', 'error')
                    return render_template('auth/login.html', csrf_token=generate_csrf)
                if not user.get('is_active', True):
                    flash('Hesabınız deaktif edilmiş!', 'error')
                    return render_template('auth/login.html', csrf_token=generate_csrf)
                # --- SHA-256 → bcrypt otomatik yükseltme ---
                new_bcrypt_hash = generate_password_hash(password)
                user['password'] = new_bcrypt_hash
                user.pop('password_hash', None)  # Eski güvensiz hash'i sil
                logging.info(f"Şifre hash upgrade (SHA256→bcrypt): user_id={user_id}")
                import secrets
                from firebase_realtime_transaction import atomic_update
                user['session_token'] = secrets.token_hex(32)
                atomic_update(f"users/{user_id}", lambda current: user)
                session['session_token'] = user['session_token']
                session['user_id'] = user_id
                cache_user_to_session(user)  # Session cache
                flash(f"Hoş geldiniz, {user.get('first_name','')} {user.get('last_name','')}!", 'success')
                next_page = request.args.get('next')
                if next_page and _is_safe_url(next_page):
                    return redirect(next_page)
                return redirect(url_for('dashboard.dashboard'))
            # Başarısız giriş denemesini logla - güvenlik izleme için
            logging.warning(f"Başarısız giriş denemesi: {email} - IP: {request.remote_addr}")
            flash('Geçersiz email veya şifre!', 'error')
            return render_template('auth/login.html', csrf_token=generate_csrf)
        # Kullanıcı bulunamadı veya şifre hash'i yok
        logging.warning(f"Başarısız giriş denemesi (kullanıcı yok veya şifre hash'i eksik): {email} - IP: {request.remote_addr}")
        flash('Geçersiz email veya şifre!', 'error')
        return render_template('auth/login.html', csrf_token=generate_csrf)
    
    return render_template('auth/login.html', csrf_token=generate_csrf)
# Şifremi Unuttum: Mail ile sıfırlama bağlantısı gönder
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    session.permanent = True  # Session'ı kalıcı yap (CSRF için gerekli)
    from firebase_realtime import get_data
    if request.method == 'POST':
        email = request.form.get('email')
        users = get_data('users') or {}
        user = next((u for u in users.values() if u.get('email') == email), None)
        if not user:
            flash('Bu mail sistemde kayıtlı değil.', 'error')
            return render_template('auth/forgot_password.html')
        # Token üret
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        token = s.dumps(email, salt='password-reset-salt')
        reset_url = url_for('auth.reset_password', token=token, _external=True)
        # Mail gönder
        msg = Message('Şifre Yenileme Talebi', sender=current_app.config['MAIL_DEFAULT_SENDER'], recipients=[email])
        msg.body = f"Merhaba {user.get('first_name','')} {user.get('last_name','')},\n\nŞifrenizi yenilemek için aşağıdaki bağlantıya tıklayın:\n{reset_url}\n\nEğer bu isteği siz yapmadıysanız, bu maili dikkate almayın."
        threading.Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start()
        flash('Şifre yenileme bağlantısı e-posta adresinize gönderildi.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/forgot_password.html')

# Şifre sıfırlama sayfası
@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except Exception:
        flash('Geçersiz veya süresi dolmuş bağlantı.', 'error')
        return redirect(url_for('auth.forgot_password'))
    from firebase_realtime import get_data, set_data
    users = get_data('users') or {}
    user_id = None
    user = None
    for uid, u in users.items():
        if u.get('email') == email:
            user_id = uid
            user = u
            break
    if not user:
        flash('Kullanıcı bulunamadı.', 'error')
        return redirect(url_for('auth.forgot_password'))
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if not new_password or len(new_password) < 6:
            flash('Şifre en az 6 karakter olmalı.', 'error')
            return render_template('auth/reset_password.html', token=token)
        if new_password != confirm_password:
            flash('Şifreler eşleşmiyor.', 'error')
            return render_template('auth/reset_password.html', token=token)
        from services.password_utils import hash_password_pbkdf2
        pw = hash_password_pbkdf2(new_password)
        user['password_hash'] = pw['hash']
        user['password_salt'] = pw['salt']
        user['password_iterations'] = pw['iterations']
        from firebase_realtime_transaction import atomic_update
        atomic_update(f"users/{user_id}", lambda current: user)
        flash('Şifreniz başarıyla güncellendi. Giriş yapabilirsiniz.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', token=token)


@auth_bp.route('/force-change-password', methods=['GET', 'POST'])
def force_change_password():
    """Zorunlu şifre değiştirme sayfası - admin tarafından sıfırlanmış şifreler için"""
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))
    
    from firebase_realtime import get_data
    from firebase_realtime_transaction import atomic_update
    
    users = get_data('users') or {}
    user = users.get(str(user_id))
    
    if not user:
        session.clear()
        flash('Kullanıcı bulunamadı. Lütfen tekrar giriş yapın.', 'error')
        return redirect(url_for('auth.login'))
    
    # force_password_change flag yoksa normal dashboard'a yönlendir
    if not user.get('force_password_change'):
        return redirect(url_for('dashboard.dashboard'))
    
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not new_password or len(new_password) < 6:
            flash('Şifre en az 6 karakter olmalı.', 'error')
            return render_template('auth/force_change_password.html')
        
        if new_password != confirm_password:
            flash('Şifreler eşleşmiyor.', 'error')
            return render_template('auth/force_change_password.html')
        
        from services.password_utils import hash_password_pbkdf2
        pw = hash_password_pbkdf2(new_password)
        
        def update_user_password(current):
            if not current:
                return user
            current['password_hash'] = pw['hash']
            current['password_salt'] = pw['salt']
            current['password_iterations'] = pw['iterations']
            current['force_password_change'] = False
            current['password_changed_at'] = datetime.utcnow().isoformat()
            return current
        
        atomic_update(f"users/{user_id}", update_user_password)
        
        # Cache temizle ve yenile
        clear_user_cache()
        updated_user = get_data(f'users/{user_id}')
        if updated_user:
            cache_user_to_session(updated_user)
        
        # Log şifre değişikliği
        from services.activity_logger import ActivityLogger
        ActivityLogger.log_activity(
            user_id=user_id,
            action=ActivityLogger.PASSWORD_CHANGE,
            resource=ActivityLogger.RESOURCE_AUTH,
            details='Zorunlu şifre değişikliği tamamlandı',
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        
        flash('Şifreniz başarıyla güncellendi!', 'success')
        return redirect(url_for('dashboard.dashboard'))
    
    return render_template('auth/force_change_password.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    session.permanent = True  # Session'ı kalıcı yap (CSRF için gerekli)
    from firebase_realtime import add_data, get_data, set_data
    
    if session.get('user_id'):
        return redirect(url_for('dashboard.dashboard'))
    
    if request.method == 'POST':
        # Formdan verileri al
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone = request.form.get('phone')
        kvkk_accepted = request.form.get('kvkkCheck')
        errors = []
        import re
        email_regex = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        phone_regex = r"^(\+90|0)?5\d{9}$"
        if not email or not re.match(email_regex, email):
            errors.append('Geçerli bir email adresi giriniz.')
        if phone and not re.match(phone_regex, phone):
            errors.append('Geçerli bir Türk GSM numarası giriniz. (05XXXXXXXXX veya +905XXXXXXXXX)')
        if not password or len(password) < 6:
            errors.append('Şifre en az 6 karakter olmalıdır.')
        if password != confirm_password:
            errors.append('Şifreler eşleşmiyor.')
        if not first_name or not last_name:
            errors.append('Ad ve soyad gerekli.')
        from firebase_realtime import get_data
        users = get_data('users') or {}
        if any(u.get('email') == email for u in users.values()):
            errors.append('Bu email adresi zaten kullanımda.')
        # Telefon numarası kontrolü - aynı numara ile kayıt engelle
        if phone and any(u.get('phone') == phone for u in users.values()):
            errors.append('Bu telefon numarası zaten kullanımda.')
        if not kvkk_accepted:
            errors.append('Gizlilik ve KVKK hüküm ve koşullarını kabul etmelisiniz.')
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('auth/register.html')
        # Benzersiz unique_link üret
        import random
        import string
        def generate_unique_link():
            # Türkçe karakterleri ASCII'ye çevir
            tr_map = str.maketrans('çğıöşüÇĞİÖŞÜ', 'cgiosuCGIOSU')
            base = (first_name + last_name).translate(tr_map).lower().replace(' ', '')
            # Sadece alfanümerik ASCII karakterleri koru
            base = ''.join(c for c in base if c.isascii() and c.isalnum())
            suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
            return f"{base}{suffix}"
        unique_link = generate_unique_link()
        while any(u.get('unique_link') == unique_link for u in users.values()):
            unique_link = generate_unique_link()
        # PBKDF2 ile parola hashle
        from services.password_utils import hash_password_pbkdf2
        pw = hash_password_pbkdf2(password)
        import uuid
        user_id = str(uuid.uuid4())
        
        # Çalışma saatlerini formdan al veya varsayılan kullan
        working_hours = parse_working_hours_from_form(request.form)
        # Eğer hiçbir gün seçilmediyse varsayılan kullan
        if not any(day.get('enabled') for day in working_hours.values()):
            working_hours = get_default_working_hours()
        
        user_data = {
            'id': user_id,
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'phone': phone,
            'unique_link': unique_link,
            'kvkk_accepted_at': str(datetime.utcnow()) if kvkk_accepted else None,
            'created_at': datetime.utcnow().isoformat(),
            'password_hash': pw['hash'],
            'password_salt': pw['salt'],
            'password_iterations': pw['iterations'],
            'is_active': True,
            'subscription_status': 'pending',  # pending, trial, active, expired
            'trial_ends_at': None,  # Deneme sürümü başlatıldığında set edilecek
            'working_hours': working_hours,
            'onboarding_completed': False  # Onboarding sihirbazı henüz tamamlanmadı
        }
        try:
            from firebase_realtime_transaction import atomic_update
            atomic_update(f'users/{user_id}', lambda current: user_data)
            
            # Auto-login user after registration
            import secrets
            session_token = secrets.token_hex(32)
            user_data['session_token'] = session_token
            atomic_update(f'users/{user_id}', lambda current: user_data)
            
            session['user_id'] = user_id
            session['session_token'] = session_token
            cache_user_to_session(user_data)
            
            # Log kayıt
            from services.activity_logger import ActivityLogger
            ActivityLogger.log_activity(
                user_id=user_id,
                action=ActivityLogger.REGISTER,
                resource=ActivityLogger.RESOURCE_AUTH,
                details='Yeni kullanıcı kaydı',
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            
            flash('Kayıt başarılı! Lütfen bir abonelik planı seçin.', 'success')
            return redirect(url_for('subscription.pricing'))
        except Exception as e:
            print(f"Kayıt hatası: {e}")  # Debug için
            flash(f'Kayıt sırasında bir hata oluştu: {str(e)}', 'error')
    return render_template('auth/register.html')

@auth_bp.route('/logout')
def logout():
    user_id = session.get('user_id')
    # Log çıkış
    if user_id:
        from services.activity_logger import ActivityLogger
        ActivityLogger.log_activity(
            user_id=user_id,
            action=ActivityLogger.LOGOUT,
            resource=ActivityLogger.RESOURCE_AUTH,
            details='Kullanıcı çıkışı',
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
    clear_user_cache()  # Clear session cache
    session.pop('user_id', None)
    session.pop('session_token', None)
    flash('Başarıyla çıkış yaptınız.', 'info')
    return redirect(url_for('index'))

@auth_bp.route('/profile')
def profile():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    # Cache'den kullanıcı bilgilerini al
    user = get_cached_user()
    
    # Get subscription info
    from services.iyzico_service import get_iyzico_service
    iyzico = get_iyzico_service()
    subscription = iyzico.get_user_subscription(str(session['user_id']))
    
    return render_template('auth/profile.html', user=user, subscription=subscription)

@auth_bp.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    from firebase_realtime import get_data, set_data
    users = get_data('users') or {}
    user = users.get(str(session.get('user_id')))
    
    if not user:
        flash('Kullanıcı bulunamadı!', 'error')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        # Temel bilgileri güncelle
        import re
        email_regex = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        phone_regex = r"^(\+90|0)?5\d{9}$"
        new_email = request.form.get('email', user.get('email', ''))
        new_phone = request.form.get('phone', user.get('phone', ''))
        if new_email and not re.match(email_regex, new_email):
            flash('Geçerli bir email adresi giriniz.', 'error')
            return render_template('auth/edit_profile.html', user=user, csrf_token=generate_csrf)
        if new_phone and not re.match(phone_regex, new_phone):
            flash('Geçerli bir Türk GSM numarası giriniz. (05XXXXXXXXX veya +905XXXXXXXXX)', 'error')
            return render_template('auth/edit_profile.html', user=user, csrf_token=generate_csrf)
        user['first_name'] = request.form.get('first_name', user.get('first_name', ''))
        user['last_name'] = request.form.get('last_name', user.get('last_name', ''))
        user['email'] = new_email
        user['phone'] = new_phone
        user['company_name'] = request.form.get('company_name', user.get('company_name', ''))
        user['updated_at'] = datetime.utcnow().isoformat()

        # Çalışma saatlerini güncelle
        working_hours = parse_working_hours_from_form(request.form)
        # Eğer form'dan gelen veriler boşsa mevcut saatleri koru
        if any(day.get('enabled') for day in working_hours.values()):
            user['working_hours'] = working_hours
        elif not user.get('working_hours'):
            user['working_hours'] = get_default_working_hours()

        # Şifre değiştirme işlemi
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if current_password or new_password or confirm_password:
            if not current_password or not new_password or not confirm_password:
                flash('Şifre değiştirmek için tüm şifre alanlarını doldurun.', 'error')
                return render_template('auth/edit_profile.html', user=user, csrf_token=generate_csrf)
            
            # PBKDF2 ile mevcut şifreyi doğrula
            from services.password_utils import verify_password_pbkdf2, hash_password_pbkdf2
            if user.get('password_hash') and user.get('password_salt') and user.get('password_iterations'):
                if not verify_password_pbkdf2(current_password, user['password_hash'], user['password_salt'], int(user['password_iterations'])):
                    flash('Mevcut şifre yanlış.', 'error')
                    return render_template('auth/edit_profile.html', user=user, csrf_token=generate_csrf)
            else:
                # Eski SHA256 hash ile kayıtlı kullanıcılar için geriye dönük uyumluluk
                import hashlib
                current_hash = hashlib.sha256(current_password.encode()).hexdigest()
                if user.get('password_hash') != current_hash:
                    flash('Mevcut şifre yanlış.', 'error')
                    return render_template('auth/edit_profile.html', user=user, csrf_token=generate_csrf)

            if new_password != confirm_password:
                flash('Yeni şifreler eşleşmiyor.', 'error')
                return render_template('auth/edit_profile.html', user=user, csrf_token=generate_csrf)

            if len(new_password) < 6:
                flash('Yeni şifre en az 6 karakter olmalı.', 'error')
                return render_template('auth/edit_profile.html', user=user, csrf_token=generate_csrf)

            pw = hash_password_pbkdf2(new_password)
            user['password_hash'] = pw['hash']
            user['password_salt'] = pw['salt']
            user['password_iterations'] = pw['iterations']

        # Logo dosyası yükleme (güvenli)
        logo_file = request.files.get('logo')
        if logo_file and logo_file.filename:
            import os
            import uuid
            from werkzeug.utils import secure_filename

            # 1. İzin verilen uzantılar (sadece resim)
            ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB

            # Orijinal dosya adından uzantıyı al (secure_filename Türkçe karakterleri silebilir)
            raw_filename = logo_file.filename
            ext = raw_filename.rsplit('.', 1)[-1].lower() if '.' in raw_filename else ''

            if not ext or ext not in ALLOWED_EXTENSIONS:
                flash('Sadece resim dosyaları yüklenebilir (png, jpg, jpeg, gif, webp).', 'error')
                return render_template('auth/edit_profile.html', user=user, csrf_token=generate_csrf)

            # 2. Dosya boyutu kontrolü
            logo_file.seek(0, 2)  # dosya sonuna git
            file_size = logo_file.tell()
            logo_file.seek(0)  # başa geri dön
            if file_size > MAX_FILE_SIZE:
                flash('Dosya boyutu en fazla 2 MB olabilir.', 'error')
                return render_template('auth/edit_profile.html', user=user, csrf_token=generate_csrf)

            # 3. MIME type doğrulama (magic bytes)
            header = logo_file.read(16)
            logo_file.seek(0)
            MAGIC_BYTES = {
                b'\x89PNG': 'png',
                b'\xff\xd8\xff': 'jpg',
                b'GIF87a': 'gif',
                b'GIF89a': 'gif',
                b'RIFF': 'webp',
            }
            is_valid_image = any(header.startswith(magic) for magic in MAGIC_BYTES)
            if not is_valid_image:
                flash('Geçersiz dosya içeriği. Lütfen gerçek bir resim dosyası yükleyin.', 'error')
                return render_template('auth/edit_profile.html', user=user, csrf_token=generate_csrf)

            # 4. Güvenli dosya adı (UUID ile çakışma önleme)
            safe_filename = f"{uuid.uuid4().hex}.{ext}"
            upload_folder = os.path.join('static', 'uploads')
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            save_path = os.path.join(upload_folder, safe_filename)
            logo_file.save(save_path)

            # 5. Eski logoyu sil (varsa)
            old_logo = user.get('logo_path')
            if old_logo:
                old_path = os.path.join(upload_folder, old_logo)
                if os.path.exists(old_path) and os.path.isfile(old_path):
                    try:
                        os.remove(old_path)
                    except OSError:
                        pass

            user['logo_path'] = safe_filename

        # Email kontrolü - başka bir kullanıcı tarafından kullanılıp kullanılmadığını kontrol et
        new_email = user.get('email')
        if new_email:
            for uid, other_user in users.items():
                if uid != str(session.get('user_id')) and other_user.get('email') == new_email:
                    flash('Bu email adresi zaten kullanımda.', 'error')
                    return render_template('auth/edit_profile.html', user=user, csrf_token=generate_csrf)

        # Telefon kontrolü - başka bir kullanıcı tarafından kullanılıp kullanılmadığını kontrol et
        new_phone = user.get('phone')
        if new_phone:
            for uid, other_user in users.items():
                if uid != str(session.get('user_id')) and other_user.get('phone') == new_phone:
                    flash('Bu telefon numarası zaten kullanımda.', 'error')
                    return render_template('auth/edit_profile.html', user=user, csrf_token=generate_csrf)

        try:
            from firebase_realtime_transaction import atomic_update
            atomic_update(f"users/{session.get('user_id')}", lambda current: user)
            cache_user_to_session(user)  # Cache yenile
            flash('Profil başarıyla güncellendi.', 'success')
            return redirect(url_for('auth.profile'))
        except Exception as e:
            flash('Profil güncellenirken bir hata oluştu.', 'error')
    
    return render_template('auth/edit_profile.html', user=user, csrf_token=generate_csrf)

@auth_bp.route('/firebase-login')
def firebase_login():
    """Renders the new Firebase-based login test page."""
    return render_template('auth/firebase_login.html')
