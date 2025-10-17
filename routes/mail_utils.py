from flask_mail import Message
from flask import url_for, current_app
from itsdangerous import URLSafeTimedSerializer

from app import app, mail
from models import User, db

def generate_reset_token(email, expires_sec=3600):
    s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    return s.dumps(email, salt='password-reset-salt')

def verify_reset_token(token, expires_sec=3600):
    s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=expires_sec)
    except Exception:
        return None
    return email

def send_reset_email(user):
    token = generate_reset_token(user.email)
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    msg = Message('Şifre Yenileme Talebi',
                  sender=current_app.config['MAIL_DEFAULT_SENDER'],
                  recipients=[user.email])
    msg.body = f"Merhaba {user.get_full_name()},\n\nŞifrenizi yenilemek için aşağıdaki bağlantıya tıklayın:\n{reset_url}\n\nEğer bu isteği siz yapmadıysanız, bu maili dikkate almayın."
    mail.send(msg)
