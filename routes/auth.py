from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_wtf.csrf import generate_csrf
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from datetime import datetime
import secrets, os, random, string, threading

auth_bp = Blueprint('auth', __name__)

# ------------------ Yardımcı Fonksiyonlar ------------------

def send_async_email(app, msg):
    """Mail gönderimini ayrı thread üzerinde çalıştırır."""
    with app.app_context():
        try:
            mail = current_app.extensions['mail']
            mail.send(msg)
        except Exception as e:
            print(f"[MAIL HATASI]: {e}")

def send_reset_email(user, token):
    """Şifre sıfırlama mailini kullanıcıya gönderir."""
    app = current_app._get_current_object()
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    msg = Message(
        subject="Şifre Yenileme Talebi",
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[user.email]
    )
    msg.body = f"""
Merhaba {user.get_full_name()},

Şifrenizi yenilemek için aşağıdaki bağlantıya tıklayın:
{reset_url}

Bu isteği siz yapmadıysanız bu maili dikkate almayın.
"""
    threading.Thread(target=send_async_email, args=(app, msg)).start()

def generate_unique_link(username):
    """Kullanıcıya benzersiz kısa link üretir."""
    base = username.lower().replace(' ', '')
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{base}{suffix}"

# ------------------ Giriş ------------------

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    from models import User, db

    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = bool(request.form.get('remember'))

        if not username or not password:
            flash('Kullanıcı adı ve şifre gerekli!', 'error')
            return render_template('auth/login.html')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('Hesabınız deaktif edilmiş!', 'error')
                return render_template('auth/login.html')

            user.session_token = secrets.token_hex(32)
            db.session.commit()
            session['session_token'] = user.session_token
            login_user(user, remember=remember)
            flash(f'Hoş geldiniz, {user.get_full_name()}!', 'success')
            return redirect(request.args.get('next') or url_for('dashboard.dashboard'))

        flash('Geçersiz kullanıcı adı veya şifre!', 'error')

    return render_template('auth/login.html')

# ------------------ Şifremi Unuttum ------------------

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    from models import User

    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if not user:
            flash('Bu e-posta adresi sistemde kayıtlı değil.', 'error')
            return render_template('auth/forgot_password.html')

        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        token = s.dumps(email, salt='password-reset-salt')

        send_reset_email(user, token)
        flash('Şifre yenileme bağlantısı e-posta adresinize gönderildi.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')

# ------------------ Şifre Sıfırlama ------------------

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    from models import User, db
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

    try:
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except (SignatureExpired, BadSignature):
        flash('Geçersiz veya süresi dolmuş bağlantı.', 'error')
        return redirect(url_for('auth.forgot_password'))

    user = User.query.filter_by(email=email).first()
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

        user.set_password(new_password)
        db.session.commit()
        flash('Şifreniz başarıyla güncellendi. Giriş yapabilirsiniz.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)

# ------------------ Kayıt ------------------

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    from models import User, db

    if current_user.is_authenticated:
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

        errors = []

        if not username or len(username) < 3:
            errors.append('Kullanıcı adı en az 3 karakter olmalı.')
        if not email or '@' not in email:
            errors.append('Geçerli bir e-posta adresi giriniz.')
        if not password or len(password) < 6:
            errors.append('Şifre en az 6 karakter olmalı.')
        if password != confirm_password:
            errors.append('Şifreler eşleşmiyor.')
        if not first_name or not last_name:
            errors.append('Ad ve soyad gerekli.')
        if not kvkk_accepted:
            errors.append('KVKK onayı gereklidir.')

        if User.query.filter_by(username=username).first():
            errors.append('Bu kullanıcı adı zaten kullanımda.')
        if User.query.filter_by(email=email).first():
            errors.append('Bu e-posta zaten kullanımda.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('auth/register.html')

        # Benzersiz link üret
        unique_link = generate_unique_link(username)
        while User.query.filter_by(unique_link=unique_link).first():
            unique_link = generate_unique_link(username)

        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            unique_link=unique_link,
            kvkk_accepted_at=datetime.utcnow()
        )
        user.set_password(password)

        try:
            db.session.add(user)
            db.session.commit()
            flash(f'Kayıt başarılı! Randevu linkiniz: /r/{user.unique_link}', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Kayıt sırasında hata: {e}', 'error')

    return render_template('auth/register.html')

# ------------------ Profil ------------------

@auth_bp.route('/profile')
@login_required
def profile():
    return render_template('auth/profile.html', user=current_user)

@auth_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    from models import User, db

    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name', current_user.first_name)
        current_user.last_name = request.form.get('last_name', current_user.last_name)
        current_user.email = request.form.get('email', current_user.email)
        current_user.phone = request.form.get('phone', current_user.phone)
        current_user.company_name = request.form.get('company_name', current_user.company_name)
        current_user.updated_at = datetime.utcnow()

        # Logo yükleme
        logo_file = request.files.get('logo')
        if logo_file and logo_file.filename:
            upload_folder = os.path.join('static', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            filename = secure_filename(logo_file.filename)
            logo_file.save(os.path.join(upload_folder, filename))
            current_user.logo_path = filename

        # Şifre değişimi
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if any([current_password, new_password, confirm_password]):
            if not all([current_password, new_password, confirm_password]):
                flash('Tüm şifre alanlarını doldurun.', 'error')
                return render_template('auth/edit_profile.html', user=current_user, csrf_token=generate_csrf)
            if not current_user.check_password(current_password):
                flash('Mevcut şifre yanlış.', 'error')
                return render_template('auth/edit_profile.html', user=current_user, csrf_token=generate_csrf)
            if new_password != confirm_password:
                flash('Yeni şifreler eşleşmiyor.', 'error')
                return render_template('auth/edit_profile.html', user=current_user, csrf_token=generate_csrf)
            if len(new_password) < 6:
                flash('Yeni şifre en az 6 karakter olmalı.', 'error')
                return render_template('auth/edit_profile.html', user=current_user, csrf_token=generate_csrf)
            current_user.set_password(new_password)

        try:
            db.session.commit()
            flash('Profil başarıyla güncellendi.', 'success')
            return redirect(url_for('auth.profile'))
        except Exception:
            db.session.rollback()
            flash('Profil güncellenirken bir hata oluştu.', 'error')

    return render_template('auth/edit_profile.html', user=current_user, csrf_token=generate_csrf)

# ------------------ Çıkış ------------------

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Başarıyla çıkış yaptınız.', 'info')
    return redirect(url_for('index'))
