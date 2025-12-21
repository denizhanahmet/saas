from datetime import date, datetime as dt, timedelta
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
    start = (page-1)*per_page
    end = start+per_page
    paged_users = users_list[start:end]
    return render_template('admin/users.html',
                         users=paged_users,
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
        flash(f"Kullanıcının SMS kotası {new_quota} olarak güncellendi.", 'success')
    except Exception as e:
        flash(f'Hata: {str(e)}', 'error')
    return redirect(url_for('admin.quota_management'))
