import threading


def send_async_email(app, msg):
    with app.app_context():
        current_app.extensions['mail'].send(msg)
from datetime import datetime

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, session, url_for)
# Flask-Login kaldırıldı, session tabanlı custom oturum yönetimi kullanıyoruz
from flask_mail import Message
from flask_wtf.csrf import generate_csrf
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Session tabanlı oturum kontrolü
    session.permanent = True  # Session'ı kalıcı yap (CSRF için gerekli)
    
    if session.get('user_id'):
        return redirect(url_for('dashboard.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = bool(request.form.get('remember'))
        
        if not username or not password:
            flash('Kullanıcı adı ve şifre gerekli!', 'error')
            return render_template('auth/login.html')
        
        from firebase_realtime import get_data
        users = get_data('users') or {}
        user = next((u for u in users.values() if u.get('username') == username), None)
        from services.password_utils import verify_password_pbkdf2
        # PBKDF2 ile hashlenmiş kullanıcılar
        if user and user.get('password_hash') and user.get('password_salt') and user.get('password_iterations'):
            if verify_password_pbkdf2(password, user['password_hash'], user['password_salt'], int(user['password_iterations'])):
                if not user.get('is_active', True):
                    flash('Hesabınız deaktif edilmiş!', 'error')
                    return render_template('auth/login.html')
                import secrets
                from firebase_realtime import set_data
                user['session_token'] = secrets.token_hex(32)
                user_id = user.get('id')
                if not user_id:
                    flash('Kullanıcı kaydında eksik id. Lütfen tekrar kayıt olun.', 'error')
                    return render_template('auth/login.html')
                from firebase_realtime_transaction import atomic_update
                atomic_update(f"users/{user_id}", lambda current: user)
                session['session_token'] = user['session_token']
                session['user_id'] = user_id
                flash(f"Hoş geldiniz, {user.get('first_name','')} {user.get('last_name','')}!", 'success')
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('dashboard.dashboard'))
            flash('Geçersiz kullanıcı adı veya şifre!', 'error')
            return render_template('auth/login.html')
        # SHA256 ile hashlenmiş eski kullanıcılar
        elif user and user.get('password_hash'):
            import hashlib
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            if user.get('password_hash') == password_hash:
                user_id = user.get('id')
                if not user_id:
                    flash('Kullanıcı kaydında eksik id. Lütfen tekrar kayıt olun.', 'error')
                    return render_template('auth/login.html')
                flash('Parola güvenliği için lütfen şifrenizi değiştirin.', 'warning')
                if not user.get('is_active', True):
                    flash('Hesabınız deaktif edilmiş!', 'error')
                    return render_template('auth/login.html')
                import secrets
                from firebase_realtime import set_data
                user['session_token'] = secrets.token_hex(32)
                from firebase_realtime_transaction import atomic_update
                atomic_update(f"users/{user_id}", lambda current: user)
                session['session_token'] = user['session_token']
                session['user_id'] = user_id
                flash(f"Hoş geldiniz, {user.get('first_name','')} {user.get('last_name','')}!", 'success')
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('dashboard.dashboard'))
            flash('Geçersiz kullanıcı adı veya şifre!', 'error')
            return render_template('auth/login.html')
        else:
            flash('Geçersiz kullanıcı adı veya şifre!', 'error')
            return render_template('auth/login.html')
    
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
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    session.permanent = True  # Session'ı kalıcı yap (CSRF için gerekli)
    from firebase_realtime import add_data, get_data, set_data
    
    if session.get('user_id'):
        return redirect(url_for('dashboard.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone = request.form.get('phone')
        kvkk_accepted = request.form.get('kvkkCheck')
        
        # Validasyonlar
        errors = []
        
        if not username or len(username) < 3:
            errors.append('Kullanıcı adı en az 3 karakter olmalıdır.')
        
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
        
        # Kullanıcı adı ve email kontrolü (Firebase'de benzersizliği kontrol et)
        users = get_data('users') or {}
        if any(u.get('username') == username for u in users.values()):
            errors.append('Bu kullanıcı adı zaten kullanımda.')
        if any(u.get('email') == email for u in users.values()):
            errors.append('Bu email adresi zaten kullanımda.')
        
        if not kvkk_accepted:
            errors.append('Gizlilik ve KVKK hüküm ve koşullarını kabul etmelisiniz.')
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('auth/register.html')
        
        # Benzersiz unique_link üret
        import random
        import string
        from services.password_utils import hash_password_pbkdf2
        def generate_unique_link(username):
            base = username.lower().replace(' ', '')
            suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
            return f"{base}{suffix}"

        unique_link = generate_unique_link(username)
        # Çakışma kontrolü (Firebase üzerinde)
        while any(u.get('unique_link') == unique_link for u in users.values()):
            unique_link = generate_unique_link(username)

        # PBKDF2 ile parola hashle
        pw = hash_password_pbkdf2(password)
        import uuid
        user_id = str(uuid.uuid4())
        user_data = {
            'id': user_id,
            'username': username,
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'phone': phone,
            'unique_link': unique_link,
            'kvkk_accepted_at': str(datetime.utcnow()) if kvkk_accepted else None,
            'password_hash': pw['hash'],
            'password_salt': pw['salt'],
            'password_iterations': pw['iterations']
        }
        try:
            from firebase_realtime_transaction import atomic_update
            atomic_update(f'users/{user_id}', lambda current: user_data)
            flash(f'Kayıt başarılı! Randevu linkiniz: /r/{unique_link}', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            print(f"Kayıt hatası: {e}")  # Debug için
            flash(f'Kayıt sırasında bir hata oluştu: {str(e)}', 'error')
    
    return render_template('auth/register.html')

@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('session_token', None)
    flash('Başarıyla çıkış yaptınız.', 'info')
    return redirect(url_for('index'))

@auth_bp.route('/profile')
def profile():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    from firebase_realtime import get_data
    users = get_data('users') or {}
    user = users.get(str(session.get('user_id')))
    return render_template('auth/profile.html', user=user)

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

        # Logo dosyası yükleme
        logo_file = request.files.get('logo')
        if logo_file and logo_file.filename:
            import os
            from werkzeug.utils import secure_filename
            upload_folder = os.path.join('static', 'uploads')
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            filename = secure_filename(logo_file.filename)
            save_path = os.path.join(upload_folder, filename)
            logo_file.save(save_path)
            user['logo_path'] = filename

        # Email kontrolü - başka bir kullanıcı tarafından kullanılıp kullanılmadığını kontrol et
        new_email = user.get('email')
        if new_email:
            for uid, other_user in users.items():
                if uid != str(session.get('user_id')) and other_user.get('email') == new_email:
                    flash('Bu email adresi zaten kullanımda.', 'error')
                    return render_template('auth/edit_profile.html', user=user, csrf_token=generate_csrf)

        try:
            from firebase_realtime_transaction import atomic_update
            atomic_update(f"users/{session.get('user_id')}", lambda current: user)
            flash('Profil başarıyla güncellendi.', 'success')
            return redirect(url_for('auth.profile'))
        except Exception as e:
            flash('Profil güncellenirken bir hata oluştu.', 'error')
    
    return render_template('auth/edit_profile.html', user=user, csrf_token=generate_csrf)
