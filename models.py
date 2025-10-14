from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date, time
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20))
    role = db.Column(db.String(20), default='customer')
    is_active = db.Column(db.Boolean, default=True)
    company_name = db.Column(db.String(100))
    logo_path = db.Column(db.String(200))
    sms_quota = db.Column(db.Integer, default=100)
    is_admin = db.Column(db.Boolean, default=False)
    unique_link = db.Column(db.String(50), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    appointments = db.relationship('Appointment', backref='user', lazy=True, cascade='all, delete-orphan')
    blocked_days = db.relationship('BlockedDay', backref='user', lazy=True, cascade='all, delete-orphan')
    clients = db.relationship('Client', backref='user', lazy=True, cascade='all, delete-orphan')
    sms_logs = db.relationship('SmsLog', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def get_upcoming_appointments(self, limit=5):
        return Appointment.query.filter(
            Appointment.user_id == self.id,
            Appointment.appointment_date >= datetime.now().date()
        ).order_by(Appointment.appointment_date.asc()).limit(limit).all()

    def get_appointments_count(self):
        return Appointment.query.filter_by(user_id=self.id).count()

    def get_remaining_sms_quota(self):
        current_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        used_sms = SmsLog.query.filter(
            SmsLog.user_id == self.id,
            SmsLog.timestamp >= current_month
        ).count()
        return max(0, self.sms_quota - used_sms)

    def get_company_display_name(self):
        return self.company_name if self.company_name else self.get_full_name()

    def is_admin_user(self):
        return self.is_admin

    def __repr__(self):
        return f'<User {self.username}>'

class Appointment(db.Model):
    __tablename__ = 'appointment'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.Time, nullable=False)
    duration = db.Column(db.Integer, default=60)
    status = db.Column(db.String(20), default='pending')
    location = db.Column(db.String(200))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_datetime(self):
        return datetime.combine(self.appointment_date, self.appointment_time)

    def is_past(self):
        return self.get_datetime() < datetime.now()

    def is_today(self):
        return self.appointment_date == date.today()

    def is_upcoming(self):
        return self.get_datetime() > datetime.now()

    def get_status_badge_class(self):
        status_classes = {
            'scheduled': 'bg-primary',
            'completed': 'bg-success',
            'cancelled': 'bg-danger'
        }
        return status_classes.get(self.status, 'bg-secondary')

    def get_status_text(self):
        status_texts = {
            'scheduled': 'Planlandı',
            'completed': 'Tamamlandı',
            'cancelled': 'İptal Edildi'
        }
        return status_texts.get(self.status, 'Bilinmiyor')

    @staticmethod
    def get_today_appointments(user_id=None):
        query = Appointment.query.filter(Appointment.appointment_date == date.today())
        if user_id:
            query = query.filter(Appointment.user_id == user_id)
        return query.order_by(Appointment.appointment_time.asc()).all()

    @staticmethod
    def get_upcoming_appointments(user_id=None, limit=10):
        query = Appointment.query.filter(
            Appointment.appointment_date >= date.today(),
            Appointment.status == 'scheduled'
        )
        if user_id:
            query = query.filter(Appointment.user_id == user_id)
        return query.order_by(Appointment.appointment_date.asc(), Appointment.appointment_time.asc()).limit(limit).all()

    def __repr__(self):
        return f'<Appointment {self.title} - {self.appointment_date}>'

class BlockedDay(db.Model):
    __tablename__ = 'blocked_day'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def is_past(self):
        return self.date < date.today()

    def is_today(self):
        return self.date == date.today()

    def is_future(self):
        return self.date > date.today()

    @staticmethod
    def is_date_blocked(user_id, check_date):
        return BlockedDay.query.filter(
            BlockedDay.user_id == user_id,
            BlockedDay.date == check_date
        ).first() is not None

    @staticmethod
    def get_blocked_days_for_user(user_id, start_date=None, end_date=None):
        query = BlockedDay.query.filter(BlockedDay.user_id == user_id)
        if start_date:
            query = query.filter(BlockedDay.date >= start_date)
        if end_date:
            query = query.filter(BlockedDay.date <= end_date)
        return query.order_by(BlockedDay.date.asc()).all()

    def __repr__(self):
        return f'<BlockedDay {self.date} - {self.reason or "No reason"}>'

class Client(db.Model):
    __tablename__ = 'client'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120))
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    appointments = db.relationship('Appointment', backref='client', lazy=True)
    sms_logs = db.relationship('SmsLog', backref='client', lazy=True)

    def get_appointments_count(self):
        return Appointment.query.filter(Appointment.client_id == self.id).count()

    def get_upcoming_appointments(self, limit=5):
        return Appointment.query.filter(
            Appointment.client_id == self.id,
            Appointment.appointment_date >= date.today(),
            Appointment.status == 'scheduled'
        ).order_by(Appointment.appointment_date.asc()).limit(limit).all()

    def get_contact_info(self):
        contact = f"{self.name} - {self.phone}"
        if self.email:
            contact += f" ({self.email})"
        return contact

    @staticmethod
    def search_clients(user_id, search_term):
        return Client.query.filter(
            Client.user_id == user_id,
            Client.is_active == True,
            db.or_(
                Client.name.contains(search_term),
                Client.phone.contains(search_term),
                Client.email.contains(search_term)
            )
        ).order_by(Client.name.asc()).all()

    def __repr__(self):
        return f'<Client {self.name} - {self.phone}>'

class SmsLog(db.Model):
    __tablename__ = 'sms_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')
    error_message = db.Column(db.Text)
    sms_provider = db.Column(db.String(50))
    cost = db.Column(db.Float, default=0.0)

    def get_status_badge_class(self):
        status_classes = {
            'pending': 'bg-warning',
            'sent': 'bg-info',
            'delivered': 'bg-success',
            'failed': 'bg-danger'
        }
        return status_classes.get(self.status, 'bg-secondary')

    def get_status_text(self):
        status_texts = {
            'pending': 'Beklemede',
            'sent': 'Gönderildi',
            'delivered': 'Teslim Edildi',
            'failed': 'Başarısız'
        }
        return status_texts.get(self.status, 'Bilinmiyor')

    def is_successful(self):
        return self.status in ['sent', 'delivered']

    def is_failed(self):
        return self.status == 'failed'

    @staticmethod
    def get_user_sms_stats(user_id, start_date=None, end_date=None):
        query = SmsLog.query.filter(SmsLog.user_id == user_id)
        if start_date:
            query = query.filter(SmsLog.timestamp >= start_date)
        if end_date:
            query = query.filter(SmsLog.timestamp <= end_date)
        total_sms = query.count()
        successful_sms = query.filter(SmsLog.status.in_(['sent', 'delivered'])).count()
        failed_sms = query.filter(SmsLog.status == 'failed').count()
        pending_sms = query.filter(SmsLog.status == 'pending').count()
        return {
            'total': total_sms,
            'successful': successful_sms,
            'failed': failed_sms,
            'pending': pending_sms,
            'success_rate': (successful_sms / total_sms * 100) if total_sms > 0 else 0
        }

    @staticmethod
    def get_recent_sms(user_id, limit=10):
        return SmsLog.query.filter(
            SmsLog.user_id == user_id
        ).order_by(SmsLog.timestamp.desc()).limit(limit).all()

    def __repr__(self):
        return f'<SmsLog {self.id} - {self.status} - {self.timestamp}>'