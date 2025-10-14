from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_wtf.csrf import generate_csrf
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    from models import User
    
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
            
            login_user(user, remember=remember)
            flash(f'Hoş geldiniz, {user.get_full_name()}!', 'success')
            
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard.dashboard'))
        else:
            flash('Geçersiz kullanıcı adı veya şifre!', 'error')
    
    return render_template('auth/login.html')

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
        
        # Validasyonlar
        errors = []
        
        if not username or len(username) < 3:
            errors.append('Kullanıcı adı en az 3 karakter olmalıdır.')
        
        if not email or '@' not in email:
            errors.append('Geçerli bir email adresi giriniz.')
        
        if not password or len(password) < 6:
            errors.append('Şifre en az 6 karakter olmalıdır.')
        
        if password != confirm_password:
            errors.append('Şifreler eşleşmiyor.')
        
        if not first_name or not last_name:
            errors.append('Ad ve soyad gerekli.')
        
        # Kullanıcı adı ve email kontrolü
        if User.query.filter_by(username=username).first():
            errors.append('Bu kullanıcı adı zaten kullanımda.')
        
        if User.query.filter_by(email=email).first():
            errors.append('Bu email adresi zaten kullanımda.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('auth/register.html')
        
        # Benzersiz unique_link üret
        import random, string
        def generate_unique_link(username):
            base = username.lower().replace(' ', '')
            suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
            return f"{base}{suffix}"

        unique_link = generate_unique_link(username)
        # Çakışma kontrolü
        from models import User as UserModel
        while UserModel.query.filter_by(unique_link=unique_link).first():
            unique_link = generate_unique_link(username)

        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            unique_link=unique_link
        )
        user.set_password(password)

        try:
            db.session.add(user)
            db.session.commit()
            flash(f'Kayıt başarılı! Randevu linkiniz: /r/{user.unique_link}', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            print(f"Kayıt hatası: {e}")  # Debug için
            flash(f'Kayıt sırasında bir hata oluştu: {str(e)}', 'error')
    
    return render_template('auth/register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Başarıyla çıkış yaptınız.', 'info')
    return redirect(url_for('index'))

@auth_bp.route('/profile')
@login_required
def profile():
    return render_template('auth/profile.html', user=current_user)

@auth_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    from models import User
    from models import db
    
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name', current_user.first_name)
        current_user.last_name = request.form.get('last_name', current_user.last_name)
        current_user.email = request.form.get('email', current_user.email)
        current_user.phone = request.form.get('phone', current_user.phone)
        current_user.updated_at = datetime.utcnow()

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
            current_user.logo_path = filename

        # Email kontrolü
        existing_user = User.query.filter_by(email=current_user.email).first()
        if existing_user and existing_user.id != current_user.id:
            flash('Bu email adresi zaten kullanımda.', 'error')
            return render_template('auth/edit_profile.html', user=current_user, csrf_token=generate_csrf())

        try:
            db.session.commit()
            flash('Profil başarıyla güncellendi.', 'success')
            return redirect(url_for('auth.profile'))
        except Exception as e:
            db.session.rollback()
            flash('Profil güncellenirken bir hata oluştu.', 'error')
    
    return render_template('auth/edit_profile.html', user=current_user, csrf_token=generate_csrf)
