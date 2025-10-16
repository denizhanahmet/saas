
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func
from models import User, Appointment, SmsLog, db

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    """Superadmin yetkisi gerektiren decorator"""
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not getattr(current_user, 'is_superadmin', False):
            flash('Bu sayfaya erişim için superadmin yetkisi gerekli!', 'error')
            return redirect(url_for('dashboard.dashboard'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@admin_bp.route('/')
@login_required
@admin_required
def admin_dashboard():
    """Admin dashboard - tüm kullanıcıların genel görünümü"""
    # Genel istatistikler
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    superadmin_users = User.query.filter_by(is_superadmin=True).count()
    total_appointments = Appointment.query.count()

    # SMS istatistikleri
    sms_stats = db.session.query(
        func.count(SmsLog.id).label('total_sms'),
        func.sum(SmsLog.cost).label('total_cost')
    ).first()

    # Kullanıcı listesi (son 10)
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()

    # Aylık kullanıcı artışı
    monthly_users = db.session.query(
        func.strftime('%Y-%m', User.created_at).label('month'),
        func.count(User.id).label('count')
    ).group_by(func.strftime('%Y-%m', User.created_at)).all()

    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         active_users=active_users,
                         superadmin_users=superadmin_users,
                         total_appointments=total_appointments,
                         sms_stats=sms_stats,
                         recent_users=recent_users,
                         monthly_users=monthly_users)

@admin_bp.route('/users')
@login_required
@admin_required
def users_list():
    """Tüm kullanıcıları listele"""
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # Filtreleme
    search = request.args.get('search', '')
    role_filter = request.args.get('role', '')
    status_filter = request.args.get('status', '')

    query = User.query

    if search:
        query = query.filter(
            db.or_(
                User.username.contains(search),
                User.email.contains(search),
                User.first_name.contains(search),
                User.last_name.contains(search)
            )
        )

    if role_filter:
        query = query.filter(User.role == role_filter)

    if status_filter == 'active':
        query = query.filter(User.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(User.is_active == False)
    elif status_filter == 'superadmin':
        query = query.filter(User.is_superadmin == True)

    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template('admin/users.html',
                         users=users,
                         search=search,
                         role_filter=role_filter,
                         status_filter=status_filter)

@admin_bp.route('/users/<int:user_id>')
@login_required
@admin_required
def user_detail(user_id):
    """Kullanıcı detayları"""
    user = User.query.get_or_404(user_id)

    # Kullanıcının randevuları
    appointments = Appointment.query.filter_by(user_id=user_id).order_by(
        Appointment.appointment_date.desc()
    ).limit(10).all()

    # Kullanıcının SMS logları
    sms_logs = SmsLog.query.filter_by(user_id=user_id).order_by(
        SmsLog.timestamp.desc()
    ).limit(10).all()

    # SMS istatistikleri
    sms_stats = SmsLog.get_user_sms_stats(user_id)

    return render_template('admin/user_detail.html',
                         user=user,
                         appointments=appointments,
                         sms_logs=sms_logs,
                         sms_stats=sms_stats)

@admin_bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    """Kullanıcı aktif/pasif durumunu değiştir"""
    user = User.query.get_or_404(user_id)

    # Kendi hesabını deaktif edemez
    if user.id == current_user.id:
        flash('Kendi hesabınızı deaktif edemezsiniz!', 'error')
        return redirect(url_for('admin.user_detail', user_id=user_id))

    user.is_active = not user.is_active
    db.session.commit()

    status = 'aktif' if user.is_active else 'deaktif'
    flash(f'Kullanıcı {status} edildi.', 'success')

    return redirect(url_for('admin.user_detail', user_id=user_id))

@admin_bp.route('/sms-usage')
@login_required
@admin_required
def sms_usage():
    """SMS kullanım istatistikleri"""
    # Tarih filtresi
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        start_date = date.today().replace(day=1)  # Bu ayın başı

    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    else:
        end_date = date.today()

    # Kullanıcı bazında SMS kullanımı
    sms_usage_by_user = db.session.query(
        User.username,
        User.email,
        User.sms_quota,
        func.count(SmsLog.id).label('sms_count'),
        func.sum(SmsLog.cost).label('total_cost')
    ).join(SmsLog, User.id == SmsLog.user_id).filter(
        SmsLog.timestamp >= start_date,
        SmsLog.timestamp <= end_date
    ).group_by(User.id).order_by(func.count(SmsLog.id).desc()).all()

    # Günlük SMS gönderimi
    daily_sms = db.session.query(
        func.date(SmsLog.timestamp).label('date'),
        func.count(SmsLog.id).label('count')
    ).filter(
        SmsLog.timestamp >= start_date,
        SmsLog.timestamp <= end_date
    ).group_by(func.date(SmsLog.timestamp)).order_by(func.date(SmsLog.timestamp)).all()

    return render_template('admin/sms_usage.html',
                         sms_usage_by_user=sms_usage_by_user,
                         daily_sms=daily_sms,
                         start_date=start_date,
                         end_date=end_date)

@admin_bp.route('/quota-management')
@login_required
@admin_required
def quota_management():
    """SMS kota yönetimi"""
    # Kullanıcılar ve kotoları
    users_with_quotas = db.session.query(
        User.id,
        User.username,
        User.email,
        User.sms_quota,
        func.count(SmsLog.id).label('used_sms')
    ).outerjoin(SmsLog, db.and_(
        User.id == SmsLog.user_id,
        func.strftime('%Y-%m', SmsLog.timestamp) == func.strftime('%Y-%m', 'now')
    )).group_by(User.id).order_by(User.sms_quota.desc()).all()

    return render_template('admin/quota_management.html',
                         users_with_quotas=users_with_quotas)

@admin_bp.route('/users/<int:user_id>/update-quota', methods=['POST'])
@login_required
@admin_required
def update_quota(user_id):
    """Kullanıcı SMS kotasını güncelle"""
    user = User.query.get_or_404(user_id)
    new_quota = request.form.get('sms_quota', type=int)

    if new_quota is None or new_quota < 0:
        flash('Geçerli bir kota değeri girin!', 'error')
        return redirect(url_for('admin.quota_management'))

    user.sms_quota = new_quota
    db.session.commit()

    flash(f'{user.username} kullanıcısının SMS kotası {new_quota} olarak güncellendi.', 'success')

    return redirect(url_for('admin.quota_management'))
