from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from models import User, Appointment, SmsLog, BlockedDay, db, Client
from sqlalchemy import func, or_, and_

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def dashboard():
    """Ana dashboard sayfası"""
    from models import User, Appointment, SmsLog, BlockedDay, db, Client
    from sqlalchemy import func
    from datetime import date
    from datetime import date
    
    user = current_user
    
    # Bugünkü randevular
    today_appointments = Appointment.get_today_appointments(user.id)
    
    # Yaklaşan randevular
    upcoming_appointments = Appointment.get_upcoming_appointments(user.id, limit=5)
    
    # İstatistikler
    total_appointments = user.get_appointments_count()
    today_count = len(today_appointments)
    upcoming_count = len(Appointment.query.filter(
        Appointment.user_id == user.id,
        Appointment.appointment_date >= date.today(),
        Appointment.status == 'scheduled'
    ).all())
    
    # Bu ayın randevuları
    start_of_month = date.today().replace(day=1)
    end_of_month = (start_of_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    monthly_appointments = Appointment.query.filter(
        Appointment.user_id == user.id,
        Appointment.appointment_date >= start_of_month,
        Appointment.appointment_date <= end_of_month
    ).all()
    
    # Durum istatistikleri
    status_stats = db.session.query(
        Appointment.status,
        func.count(Appointment.id)
    ).filter(
        Appointment.user_id == user.id
    ).group_by(Appointment.status).all()
    
    status_counts = {status: count for status, count in status_stats}
    
    return render_template('dashboard/index.html',
                         today_appointments=today_appointments,
                         upcoming_appointments=upcoming_appointments,
                         total_appointments=total_appointments,
                         today_count=today_count,
                         upcoming_count=upcoming_count,
                         monthly_appointments=monthly_appointments,
                         status_counts=status_counts,
                         date_util=date)

@dashboard_bp.route('/appointments')
@login_required
def appointments():
    """Randevular sayfası - kullanıcıya özel filtreleme"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Filtreleme parametreleri
    status_filter = request.args.get('status')
    date_filter = request.args.get('date')
    search = request.args.get('search')
    
    # Temel sorgu - sadece kullanıcının randevuları
    query = Appointment.query.filter(Appointment.user_id == current_user.id)
    
    # Durum filtresi
    if status_filter:
        query = query.filter(Appointment.status == status_filter)
    
    # Tarih filtresi
    if date_filter:
        if date_filter == 'today':
            query = query.filter(Appointment.appointment_date == date.today())
        elif date_filter == 'upcoming':
            query = query.filter(Appointment.appointment_date >= date.today())
        elif date_filter == 'past':
            query = query.filter(Appointment.appointment_date < date.today())
    
    # Arama filtresi
    if search:
        query = query.filter(
            Appointment.title.contains(search) |
            Appointment.description.contains(search)
        )
    
    # Sıralama ve sayfalama
    appointments = query.order_by(
        Appointment.appointment_date.desc(),
        Appointment.appointment_time.desc()
    ).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('dashboard/appointments.html',
                         appointments=appointments,
                         status_filter=status_filter,
                         date_filter=date_filter,
                         search=search,
                         date_util=date)

@dashboard_bp.route('/calendar')
@login_required
def calendar():
    """Takvim görünümü"""
    # Bu ayın randevuları
    today = date.today()
    start_of_month = today.replace(day=1)
    
    # Bir sonraki ayın başlangıcı
    if start_of_month.month == 12:
        next_month = start_of_month.replace(year=start_of_month.year + 1, month=1)
    else:
        next_month = start_of_month.replace(month=start_of_month.month + 1)
    
    # Bu ayın randevuları
    monthly_appointments = Appointment.query.filter(
        Appointment.user_id == current_user.id,
        Appointment.appointment_date >= start_of_month,
        Appointment.appointment_date < next_month
    ).order_by(Appointment.appointment_date.asc()).all()
    
    # Tarihe göre grupla
    appointments_by_date = {}
    for appointment in monthly_appointments:
        date_str = appointment.appointment_date.strftime('%Y-%m-%d')
        if date_str not in appointments_by_date:
            appointments_by_date[date_str] = []
        appointments_by_date[date_str].append(appointment)
    
    return render_template('dashboard/calendar.html',
                         appointments_by_date=appointments_by_date,
                         current_month=start_of_month,
                         date_util=date)

@dashboard_bp.route('/stats')
@login_required
def stats():
    """İstatistikler sayfası"""
    user = current_user

    # Genel istatistikler
    total_appointments = Appointment.query.filter_by(user_id=user.id).count()
    completed_appointments = Appointment.query.filter_by(user_id=user.id, status='completed').count()
    scheduled_appointments = Appointment.query.filter_by(user_id=user.id, status='scheduled').count()
    cancelled_appointments = Appointment.query.filter_by(user_id=user.id, status='cancelled').count()

    # Bu yılın istatistikleri
    current_year = datetime.now().year
    yearly_appointments = Appointment.query.filter(
        Appointment.user_id == user.id,
        func.extract('year', Appointment.appointment_date) == current_year
    ).all()

    # Aylık dağılım
    monthly_stats = {}
    for appointment in yearly_appointments:
        month = appointment.appointment_date.month
        if month not in monthly_stats:
            monthly_stats[month] = 0
        monthly_stats[month] += 1

    # Chart için labels ve data
    monthly_labels = [f'{month}.Ay' for month in sorted(monthly_stats.keys())]
    monthly_data = [monthly_stats[month] for month in sorted(monthly_stats.keys())]

    # Durum istatistikleri
    status_stats = db.session.query(
        Appointment.status,
        func.count(Appointment.id)
    ).filter(
        Appointment.user_id == user.id
    ).group_by(Appointment.status).all()

    # En çok randevu olan günler
    busiest_days = []
    busy_days = db.session.query(
        Appointment.appointment_date,
        func.count(Appointment.id).label('count')
    ).filter(
        Appointment.user_id == user.id
    ).group_by(Appointment.appointment_date).order_by(
        func.count(Appointment.id).desc()
    ).limit(10).all()
    for day, count in busy_days:
        busiest_days.append((day.strftime('%d.%m.%Y'), count))

    # En aktif saatler
    busiest_hours = []
    hour_stats = db.session.query(
        func.strftime('%H', Appointment.appointment_time),
        func.count(Appointment.id)
    ).filter(
        Appointment.user_id == user.id
    ).group_by(func.strftime('%H', Appointment.appointment_time)).order_by(func.count(Appointment.id).desc()).limit(10).all()
    for hour, count in hour_stats:
        busiest_hours.append((hour, count))

    stats = {
        'total_appointments': total_appointments,
        'completed_appointments': completed_appointments,
        'scheduled_appointments': scheduled_appointments,
        'cancelled_appointments': cancelled_appointments,
        'busiest_days': busiest_days,
        'busiest_hours': busiest_hours
    }

    return render_template('dashboard/stats.html',
                         stats=stats,
                         monthly_labels=monthly_labels,
                         monthly_data=monthly_data,
                         current_year=current_year,
                         date_util=date)

@dashboard_bp.route('/blocked-days')
@login_required
def blocked_days():
    """Bloklanmış günler sayfası"""
    from models import BlockedDay, db
    
    # Mevcut bloklanmış günler
    blocked_days = BlockedDay.get_blocked_days_for_user(current_user.id)
    
    # Geçmiş, bugün ve gelecek bloklanmış günleri ayır
    past_blocked = [bd for bd in blocked_days if bd.is_past()]
    today_blocked = [bd for bd in blocked_days if bd.is_today()]
    future_blocked = [bd for bd in blocked_days if bd.is_future()]
    
    from flask_wtf.csrf import generate_csrf
    return render_template('dashboard/blocked_days.html',
                         past_blocked=past_blocked,
                         today_blocked=today_blocked,
                         future_blocked=future_blocked,
                         date_util=date,
                         csrf_token=generate_csrf())

@dashboard_bp.route('/blocked-days/add', methods=['POST'])
@login_required
def add_blocked_day():
    """Bloklanmış gün ekle"""
    from app import BlockedDay, db
    
    blocked_date = request.form.get('blocked_date')
    reason = request.form.get('reason', '').strip()
    
    if not blocked_date:
        flash('Lütfen bir tarih seçin!', 'error')
        return redirect(url_for('dashboard.blocked_days'))
    
    try:
        # Tarih formatını kontrol et
        blocked_date_obj = datetime.strptime(blocked_date, '%Y-%m-%d').date()
        
        # Geçmiş tarih kontrolü
        if blocked_date_obj < date.today():
            flash('Geçmiş tarihleri bloklayamazsınız!', 'error')
            return redirect(url_for('dashboard.blocked_days'))
        
        # Zaten bloklanmış mı kontrol et
        existing_block = BlockedDay.query.filter(
            BlockedDay.user_id == current_user.id,
            BlockedDay.date == blocked_date_obj
        ).first()
        
        if existing_block:
            flash('Bu tarih zaten bloklanmış!', 'error')
            return redirect(url_for('dashboard.blocked_days'))
        
        # Yeni bloklanmış gün oluştur
        blocked_day = BlockedDay(
            user_id=current_user.id,
            date=blocked_date_obj,
            reason=reason if reason else None
        )
        
        db.session.add(blocked_day)
        db.session.commit()
        
        flash(f'{blocked_date_obj.strftime("%d.%m.%Y")} tarihi başarıyla bloklandı!', 'success')
        
    except ValueError:
        flash('Geçersiz tarih formatı!', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Hata oluştu: {str(e)}', 'error')
    
    return redirect(url_for('dashboard.blocked_days'))

@dashboard_bp.route('/blocked-days/remove/<int:blocked_day_id>', methods=['POST'])
@login_required
def remove_blocked_day(blocked_day_id):
    """Bloklanmış günü kaldır"""
    from app import BlockedDay, db
    
    blocked_day = BlockedDay.query.filter_by(
        id=blocked_day_id,
        user_id=current_user.id
    ).first()
    
    if not blocked_day:
        flash('Bloklanmış gün bulunamadı!', 'error')
        return redirect(url_for('dashboard.blocked_days'))
    
    try:
        blocked_date = blocked_day.date
        db.session.delete(blocked_day)
        db.session.commit()
        
        flash(f'{blocked_date.strftime("%d.%m.%Y")} tarihi bloklaması kaldırıldı!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Hata oluştu: {str(e)}', 'error')
    
    return redirect(url_for('dashboard.blocked_days'))

@dashboard_bp.route('/blocked-days/check')
@login_required
def check_blocked_date():
    """Tarih bloklanmış mı kontrol et (AJAX)"""
    from models import BlockedDay
    
    check_date = request.args.get('date')
    
    if not check_date:
        return jsonify({'blocked': False})
    
    try:
        check_date_obj = datetime.strptime(check_date, '%Y-%m-%d').date()
        is_blocked = BlockedDay.is_date_blocked(current_user.id, check_date_obj)
        
        return jsonify({'blocked': is_blocked})
    except ValueError:
        return jsonify({'blocked': False})
