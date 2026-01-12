from datetime import date, datetime, datetime as dt, timedelta
from flask import (Blueprint, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from firebase_realtime import get_data, set_data, update_data, delete_data

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    """Superadmin yetkisi gerektiren decorator"""
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('auth.login'))
        # Firebase'den kullanıcı bilgisi al
        from firebase_realtime import get_data
        users = get_data('users') or {}
        user = users.get(str(session.get('user_id')))
        if not user or not user.get('is_superadmin', False):
            flash('Bu sayfaya erişim için superadmin yetkisi gerekli!', 'error')
            return redirect(url_for('dashboard.dashboard'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@admin_bp.route('/')
@admin_required
def admin_dashboard():
    """Admin dashboard - tüm kullanıcıların genel görünümü"""
    # Genel istatistikler
    users = get_data('users') or {}
    appointments = get_data('appointments') or {}
    sms_logs = get_data('sms_logs') or {}
    total_users = len(users)
    active_users = sum(1 for u in users.values() if u.get('is_active'))
    superadmin_users = sum(1 for u in users.values() if u.get('is_superadmin'))
    total_appointments = len(appointments)
    total_sms = len(sms_logs)
    total_cost = sum(float(s.get('cost', 0)) for s in sms_logs.values())
    sms_stats = {'total_sms': total_sms, 'total_cost': total_cost}
    from collections import Counter
    import datetime
    def get_month(dtstr):
        try:
            return datetime.datetime.fromisoformat(dtstr).strftime('%Y-%m')
        except:
            return ''
    months = [get_month(u.get('created_at', '')) for u in users.values() if u.get('created_at')]
    monthly_users = Counter(months)
    def parse_created_at(u):
        try:
            return dt.fromisoformat(u.get('created_at', '1970-01-01T00:00:00'))
        except Exception:
            return dt(1970, 1, 1)
    recent_users = sorted(users.values(), key=parse_created_at, reverse=True)[:10]
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         active_users=active_users,
                         superadmin_users=superadmin_users,
                         total_appointments=total_appointments,
                         sms_stats=sms_stats,
                         recent_users=recent_users,
                         monthly_users=monthly_users.items())

@admin_bp.route('/users')
@admin_required
def users_list():
    """Tüm kullanıcıları listele"""
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # Filtreleme
    search = request.args.get('search', '')
    role_filter = request.args.get('role', '')
    status_filter = request.args.get('status', '')

    users = get_data('users') or {}
    users_list = list(users.values())
    if search:
        users_list = [u for u in users_list if search.lower() in (u.get('username','')+u.get('email','')+u.get('first_name','')+u.get('last_name','')).lower()]
    if role_filter:
        users_list = [u for u in users_list if u.get('role') == role_filter]
    if status_filter == 'active':
        users_list = [u for u in users_list if u.get('is_active')]
    elif status_filter == 'inactive':
        users_list = [u for u in users_list if not u.get('is_active')]
    elif status_filter == 'superadmin':
        users_list = [u for u in users_list if u.get('is_superadmin')]
    users_list = sorted(users_list, key=lambda u: u.get('created_at', ''), reverse=True)
    
    # Pagination object
    total = len(users_list)
    start = (page-1)*per_page
    end = start+per_page
    paged_users = users_list[start:end]
    
    class Pagination:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page if per_page > 0 else 0
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None
        
        def iter_pages(self, left_edge=2, left_current=2, right_current=2, right_edge=2):
            last = 0
            for num in range(1, self.pages + 1):
                if (num <= left_edge or 
                    (self.page - left_current <= num <= self.page + right_current) or 
                    num > self.pages - right_edge):
                    if last + 1 != num:
                        yield None
                    yield num
                    last = num
    
    pagination = Pagination(paged_users, page, per_page, total)
    
    return render_template('admin/users.html',
                         users=pagination,
                         search=search,
                         role_filter=role_filter,
                         status_filter=status_filter)

@admin_bp.route('/users/<user_id>')
@admin_required
def user_detail(user_id):
    """Kullanıcı detayları"""
    users = get_data('users') or {}
    user = users.get(str(user_id))
    appointments = get_data('appointments') or {}
    user_appointments = [a for a in appointments.values() if a.get('user_id') == user_id]
    user_appointments = sorted(user_appointments, key=lambda a: a.get('appointment_date', ''), reverse=True)[:10]
    sms_logs = get_data('sms_logs') or {}
    user_sms_logs = [s for s in sms_logs.values() if s.get('user_id') == user_id]
    user_sms_logs = sorted(user_sms_logs, key=lambda s: s.get('timestamp', ''), reverse=True)[:10]
    sms_stats = {
        'total_sms': len(user_sms_logs),
        'total_cost': sum(float(s.get('cost', 0)) for s in user_sms_logs)
    }
    return render_template('admin/user_detail.html',
                         user=user,
                         appointments=user_appointments,
                         sms_logs=user_sms_logs,
                         sms_stats=sms_stats)

@admin_bp.route('/users/<user_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    users = get_data('users') or {}
    user = users.get(str(user_id))
    if not user:
        flash('Kullanıcı bulunamadı.', 'error')
        return redirect(url_for('admin.users_list'))
    new_status = not user.get('is_active', False)
    from firebase_realtime_transaction import atomic_update
    def update_status(current):
        if not current:
            return user  # fallback
        current['is_active'] = new_status
        return current
    atomic_update(f"users/{user_id}", update_status)
    
    # Log kullanıcı durumu değişikliği
    from services.activity_logger import ActivityLogger
    ActivityLogger.log_activity(
        user_id=session.get('user_id'),
        action=ActivityLogger.USER_STATUS_CHANGE,
        resource=ActivityLogger.RESOURCE_USER,
        resource_id=user_id,
        details=f"Kullanıcı {'aktif' if new_status else 'pasif'} yapıldı",
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )
    
    flash('Kullanıcı durumu güncellendi.', 'success')
    return redirect(request.referrer or url_for('admin.users_list'))

@admin_bp.route('/sms-usage')
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
    users = get_data('users') or {}
    sms_logs = get_data('sms_logs') or {}
    usage = {}
    for s in sms_logs.values():
        uid = s.get('user_id')
        if not uid: continue
        if uid not in usage:
            usage[uid] = {'sms_count': 0, 'total_cost': 0}
        usage[uid]['sms_count'] += 1
        usage[uid]['total_cost'] += float(s.get('cost', 0))
    sms_usage_by_user = [
        {
            'username': users.get(str(uid), {}).get('username', ''),
            'email': users.get(str(uid), {}).get('email', ''),
            'sms_quota': users.get(str(uid), {}).get('sms_quota', 0),
            'sms_count': u['sms_count'],
            'total_cost': u['total_cost']
        }
        for uid, u in usage.items()
    ]
    from collections import Counter
    daily_sms = Counter()
    for s in sms_logs.values():
        ts = s.get('timestamp')
        if ts:
            try:
                d = str(ts)[:10]
                daily_sms[d] += 1
            except:
                pass
    daily_sms = sorted(daily_sms.items())
    return render_template('admin/sms_usage.html',
                         sms_usage_by_user=sms_usage_by_user,
                         daily_sms=daily_sms,
                         start_date=start_date,
                         end_date=end_date)

@admin_bp.route('/quota-management')
@admin_required
def quota_management():
    """SMS kota yönetimi"""
    # Kullanıcılar ve kotoları
    users = get_data('users') or {}
    sms_logs = get_data('sms_logs') or {}
    import datetime
    now = datetime.datetime.now()
    this_month = now.strftime('%Y-%m')
    usage = {}
    for s in sms_logs.values():
        uid = s.get('user_id')
        ts = s.get('timestamp', '')
        if not uid or not ts: continue
        if ts[:7] == this_month:
            usage[uid] = usage.get(uid, 0) + 1
    users_with_quotas = [
        {
            'id': uid,
            'username': u.get('username', ''),
            'email': u.get('email', ''),
            'sms_quota': u.get('sms_quota', 0),
            'used_sms': usage.get(uid, 0)
        }
        for uid, u in users.items()
    ]
    users_with_quotas = sorted(users_with_quotas, key=lambda u: u.get('sms_quota', 0), reverse=True)
    return render_template('admin/quota_management.html',
                         users_with_quotas=users_with_quotas)

@admin_bp.route('/users/<int:user_id>/update-quota', methods=['POST'])
@admin_required
def update_quota(user_id):
    """Kullanıcı SMS kotasını güncelle"""
    from firebase_realtime_transaction import atomic_update
    new_quota = request.form.get('sms_quota', type=int)
    if new_quota is None or new_quota < 0:
        flash('Geçerli bir kota değeri girin!', 'error')
        return redirect(url_for('admin.quota_management'))
    try:
        def update_fn(current):
            if not current:
                raise Exception('Kullanıcı bulunamadı!')
            current['sms_quota'] = new_quota
            return current
        updated = atomic_update(f"users/{user_id}", update_fn)
        
        # Log kota güncelleme
        from services.activity_logger import ActivityLogger
        ActivityLogger.log_activity(
            user_id=session.get('user_id'),
            action=ActivityLogger.QUOTA_UPDATE,
            resource=ActivityLogger.RESOURCE_USER,
            resource_id=str(user_id),
            details=f"SMS kotası {new_quota} olarak güncellendi",
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        
        flash(f"Kullanıcının SMS kotası {new_quota} olarak güncellendi.", 'success')
    except Exception as e:
        flash(f'Hata: {str(e)}', 'error')
    return redirect(url_for('admin.quota_management'))

# =====================
# SMS Event Management
# =====================

@admin_bp.route('/sms-events')
@admin_required
def sms_events():
    """SMS event yönetimi sayfası"""
    from services.sms_event_service import SMSEventService
    events = get_data('sms_events') or {}
    locations = SMSEventService.LOCATIONS
    return render_template('admin/sms_events.html', 
                         events=events, 
                         locations=locations)

@admin_bp.route('/sms-events/create', methods=['POST'])
@admin_required
def sms_event_create():
    """Yeni SMS event oluştur"""
    import uuid
    event_id = f"evt_{uuid.uuid4().hex[:8]}"
    event_data = {
        'location': request.form.get('location'),
        'template': request.form.get('template'),
        'order': int(request.form.get('order', 10)),
        'priority': int(request.form.get('priority', 2)),
        'enabled': request.form.get('enabled') == 'on',
        'conditions': {'has_phone': True}
    }
    set_data(f'sms_events/{event_id}', event_data)
    flash('SMS eventi başarıyla oluşturuldu.', 'success')
    return redirect(url_for('admin.sms_events'))

@admin_bp.route('/sms-events/update', methods=['POST'])
@admin_required
def sms_event_update():
    """SMS event güncelle"""
    event_id = request.form.get('event_id')
    if not event_id:
        flash('Event bulunamadı!', 'error')
        return redirect(url_for('admin.sms_events'))
    
    event_data = {
        'location': request.form.get('location'),
        'template': request.form.get('template'),
        'order': int(request.form.get('order', 10)),
        'priority': int(request.form.get('priority', 2)),
        'enabled': request.form.get('enabled') == 'on',
        'conditions': {'has_phone': True}
    }
    set_data(f'sms_events/{event_id}', event_data)
    flash('SMS eventi güncellendi.', 'success')
    return redirect(url_for('admin.sms_events'))

@admin_bp.route('/sms-events/<event_id>/toggle', methods=['POST'])
@admin_required
def sms_event_toggle(event_id):
    """SMS event durumunu değiştir"""
    events = get_data('sms_events') or {}
    event = events.get(event_id)
    if not event:
        flash('Event bulunamadı!', 'error')
        return redirect(url_for('admin.sms_events'))
    
    event['enabled'] = not event.get('enabled', True)
    set_data(f'sms_events/{event_id}', event)
    status = "aktifleştirildi" if event['enabled'] else "devre dışı bırakıldı"
    flash(f'SMS eventi {status}.', 'success')
    return redirect(url_for('admin.sms_events'))

@admin_bp.route('/sms-events/<event_id>/delete', methods=['POST'])
@admin_required
def sms_event_delete(event_id):
    """SMS event sil"""
    delete_data(f'sms_events/{event_id}')
    flash('SMS eventi silindi.', 'success')
    return redirect(url_for('admin.sms_events'))


# =====================
# Activity Logs
# =====================

@admin_bp.route('/logs')
@admin_required
def activity_logs():
    """Sistem aktivite logları sayfası"""
    from services.activity_logger import ActivityLogger
    
    # Filtreleri al
    action_filter = request.args.get('action', '')
    resource_filter = request.args.get('resource', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    page = request.args.get('page', 1, type=int)
    per_page = 25
    
    # Tüm logları çek
    all_logs = ActivityLogger.get_logs(
        limit=500,
        action_filter=action_filter if action_filter else None,
        resource_filter=resource_filter if resource_filter else None,
        start_date=start_date if start_date else None,
        end_date=end_date if end_date else None
    )
    
    # Pagination
    total = len(all_logs)
    start = (page - 1) * per_page
    end = start + per_page
    logs = all_logs[start:end]
    
    # Pagination object
    class Pagination:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page if per_page > 0 else 0
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None
        
        def iter_pages(self, left_edge=2, left_current=2, right_current=2, right_edge=2):
            last = 0
            for num in range(1, self.pages + 1):
                if (num <= left_edge or 
                    (self.page - left_current <= num <= self.page + right_current) or 
                    num > self.pages - right_edge):
                    if last + 1 != num:
                        yield None
                    yield num
                    last = num
    
    pagination = Pagination(logs, page, per_page, total)
    
    # Aksiyon ve kaynak seçenekleri
    actions = [
        ('login_success', 'Başarılı Giriş'),
        ('login_failed', 'Başarısız Giriş'),
        ('logout', 'Çıkış'),
        ('register', 'Yeni Kayıt'),
        ('password_change', 'Şifre Değişikliği'),
        ('appointment_create', 'Randevu Oluşturma'),
        ('appointment_update', 'Randevu Güncelleme'),
        ('appointment_approve', 'Randevu Onaylama'),
        ('appointment_reject', 'Randevu Reddetme'),
        ('user_status_change', 'Kullanıcı Durum Değişikliği'),
        ('quota_update', 'Kota Güncelleme'),
        ('sms_event_create', 'SMS Event Oluşturma'),
        ('sms_event_update', 'SMS Event Güncelleme'),
        ('sms_event_delete', 'SMS Event Silme'),
    ]
    
    resources = [
        ('auth', 'Kimlik Doğrulama'),
        ('appointment', 'Randevu'),
        ('user', 'Kullanıcı'),
        ('sms', 'SMS'),
        ('waitlist', 'Bekleme Listesi'),
    ]
    
    return render_template('admin/logs.html',
                         logs=pagination,
                         actions=actions,
                         resources=resources,
                         action_filter=action_filter,
                         resource_filter=resource_filter,
                         start_date=start_date,
                         end_date=end_date,
                         ActivityLogger=ActivityLogger)
