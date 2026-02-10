def get_status_badge_class(status):
    return {
        'scheduled': 'bg-primary',
        'completed': 'bg-success',
        'cancelled': 'bg-danger'
    }.get(status, 'bg-secondary')

def get_status_text(status):
    return {
        'scheduled': 'Planlandı',
        'completed': 'Tamamlandı',
        'cancelled': 'İptal Edildi'
    }.get(status, status)
from datetime import date, datetime, timedelta
from collections import defaultdict

from flask import (Blueprint, flash, jsonify, redirect, render_template,
                   request, session, url_for)

from firebase_realtime import get_data, set_data, update_data, delete_data

dashboard_bp = Blueprint('dashboard', __name__)

# Firebase'den tarih string'lerini parse etmek için yardımcı fonksiyon
def parse_date(date_str):
    """Tarih string'ini (YYYY-MM-DD) date nesnesine çevir"""
    if isinstance(date_str, str):
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return None
    return date_str

# Tarihi string'e formatlamak için yardımcı fonksiyon
def format_date(date_obj):
    """Date nesnesini YYYY-MM-DD string'ine çevir"""
    if isinstance(date_obj, date):
        return date_obj.strftime('%Y-%m-%d')
    return date_obj

# Firebase'den saat string'lerini parse etmek için yardımcı fonksiyon
def parse_time(time_str):
    """Saat string'ini (HH:MM) time nesnesine çevir"""
    if isinstance(time_str, str):
        try:
            return datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            return None
    return time_str

@dashboard_bp.route('/')
def dashboard():
    """Ana dashboard sayfası"""
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    
    user_id = str(session.get('user_id'))
    
    # Get all appointments for this user
    all_appointments_data = get_data('appointments') or {}
    user_appointments = [
        apt for apt in all_appointments_data.values()
        if str(apt.get('user_id')) == str(user_id)
    ]
    
    today = date.today()
    today_appointments = []
    upcoming_appointments = []
    total_appointments = len(user_appointments)
    
    # Process appointments
    for apt in user_appointments:
        try:
            apt_date = parse_date(apt.get('appointment_date'))
            apt_time = parse_time(apt.get('appointment_time'))
            
            if apt_date is None:
                continue
            
            # Create appointment object for template
            apt_obj = {
                'id': apt.get('id'),
                'title': apt.get('title', 'Untitled'),
                'description': apt.get('description', ''),
                'appointment_date': apt_date,
                'appointment_time': apt_time,
                'duration': apt.get('duration', 60),
                'status': apt.get('status', 'scheduled'),
                'location': apt.get('location', ''),
                'notes': apt.get('notes', ''),
            }
            
            if apt_date == today:
                today_appointments.append(apt_obj)
            elif apt_date > today:
                upcoming_appointments.append(apt_obj)
        except Exception as e:
            continue
    
    # Sort appointments
    today_appointments.sort(key=lambda x: x.get('appointment_time') or datetime.min.time())
    upcoming_appointments.sort(key=lambda x: (x.get('appointment_date'), x.get('appointment_time') or datetime.min.time()))
    upcoming_appointments = upcoming_appointments[:10]  # Limit to 10
    
    today_count = len(today_appointments)
    upcoming_count = len(upcoming_appointments)
    monthly_appointments = upcoming_appointments  # For template compatibility
    status_counts = {}
    
    # Calculate status counts for the stats cards
    completed_count = sum(1 for apt in user_appointments if apt.get('status') == 'completed')
    scheduled_count = sum(1 for apt in user_appointments if apt.get('status') in ['scheduled', 'approved'])
    
    return render_template('dashboard/index.html',
                         today_appointments=today_appointments,
                         upcoming_appointments=upcoming_appointments,
                         total_appointments=total_appointments,
                         today_count=today_count,
                         upcoming_count=upcoming_count,
                         completed_count=completed_count,
                         scheduled_count=scheduled_count,
                         monthly_appointments=monthly_appointments,
                         status_counts=status_counts,
                         date_util=date)

@dashboard_bp.route('/appointments')
def appointments():
    """Randevular sayfası - kullanıcıya özel filtreleme"""
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    
    user_id = str(session.get('user_id'))
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Filtreleme parametreleri
    status_filter = request.args.get('status_filter')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # Get all appointments
    all_appointments_data = get_data('appointments') or {}
    user_appointments = [
        apt for apt in all_appointments_data.values()
        if str(apt.get('user_id')) == str(user_id)
    ]
    
    # Apply filters
    filtered_appointments = []
    for apt in user_appointments:
        try:
            apt_date = parse_date(apt.get('appointment_date'))
            apt_time = parse_time(apt.get('appointment_time'))
            
            if apt_date is None:
                continue
            
            # Status filter
            if status_filter and apt.get('status') != status_filter:
                continue
            
            # Date range filter
            if date_from:
                try:
                    date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                    if apt_date < date_from_obj:
                        continue
                except ValueError:
                    pass
            
            if date_to:
                try:
                    date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
                    if apt_date > date_to_obj:
                        continue
                except ValueError:
                    pass
            
            # Create appointment object
            apt_obj = {
                'id': apt.get('id'),
                'title': apt.get('title', 'Untitled'),
                'description': apt.get('description', ''),
                'appointment_date': apt_date,
                'appointment_time': apt_time,
                'duration': apt.get('duration', 60),
                'status': apt.get('status', 'scheduled'),
                'location': apt.get('location', ''),
                'notes': apt.get('notes', ''),
            }
            
            filtered_appointments.append(apt_obj)
        except Exception as e:
            continue
    
    # Sort by date and time (descending)
    filtered_appointments.sort(
        key=lambda x: (x.get('appointment_date'), x.get('appointment_time') or datetime.min.time()),
        reverse=True
    )
    
    # Paginate
    total_count = len(filtered_appointments)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_appointments = filtered_appointments[start_idx:end_idx]
    
    # Create pagination object
    class PaginationObj:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None

        def iter_pages(self, left_edge=2, left_current=2, right_current=2, right_edge=2):
            last = 0
            for num in range(1, self.pages + 1):
                if (
                    num <= left_edge
                    or (self.page - left_current <= num <= self.page + right_current)
                    or num > self.pages - right_edge
                ):
                    if last + 1 != num:
                        yield None
                    yield num
                    last = num
    
    appointments_obj = PaginationObj(paginated_appointments, page, per_page, total_count)
    
    return render_template('dashboard/appointments.html',
                         appointments=appointments_obj.items,
                         pagination=appointments_obj,
                         status_filter=status_filter,
                         date_from=date_from,
                         date_to=date_to,
                         date_util=date)

@dashboard_bp.route('/calendar')
def calendar():
    """Takvim görünümü"""
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    
    user_id = str(session.get('user_id'))
    
    # Get all appointments (no month filter — FullCalendar handles navigation)
    all_appointments_data = get_data('appointments') or {}
    
    appointments = []
    for apt in all_appointments_data.values():
        if str(apt.get('user_id')) != str(user_id):
            continue
        try:
            apt_date = parse_date(apt.get('appointment_date'))
            apt_time = parse_time(apt.get('appointment_time'))
            
            if apt_date is None:
                continue
            
            appointments.append({
                'id': apt.get('id'),
                'title': apt.get('title', 'Untitled'),
                'description': apt.get('description', ''),
                'appointment_date': apt_date,
                'appointment_time': apt_time,
                'duration': apt.get('duration', 60),
                'status': apt.get('status', 'scheduled'),
                'location': apt.get('location', ''),
                'notes': apt.get('notes', ''),
            })
        except Exception:
            continue
    
    # Sort by date and time
    appointments.sort(
        key=lambda x: (x.get('appointment_date'), x.get('appointment_time') or datetime.min.time())
    )
    
    return render_template('dashboard/calendar.html',
                         appointments=appointments,
                         date_util=date)

@dashboard_bp.route('/stats')
def stats():
    """İstatistikler sayfası"""
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    
    user_id = str(session.get('user_id'))
    
    # Get all appointments
    all_appointments_data = get_data('appointments') or {}
    user_appointments = [
        apt for apt in all_appointments_data.values()
        if str(apt.get('user_id')) == str(user_id)
    ]
    
    # Process appointments
    processed_appointments = []
    for apt in user_appointments:
        try:
            apt_date = parse_date(apt.get('appointment_date'))
            apt_time = parse_time(apt.get('appointment_time'))
            
            if apt_date is None:
                continue
            
            processed_appointments.append({
                'date': apt_date,
                'time': apt_time,
                'status': apt.get('status', 'scheduled'),
            })
        except Exception as e:
            continue
    
    # General statistics
    total_appointments = len(processed_appointments)
    completed_appointments = sum(1 for apt in processed_appointments if apt['status'] == 'completed')
    scheduled_appointments = sum(1 for apt in processed_appointments if apt['status'] in ['scheduled', 'approved'])
    pending_appointments = sum(1 for apt in processed_appointments if apt['status'] == 'pending')
    cancelled_appointments = sum(1 for apt in processed_appointments if apt['status'] in ['cancelled', 'rejected'])
    
    # === WEEKLY TREND (Son 7 gün) ===
    today = date.today()
    day_names_tr = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz']
    weekly_labels = []
    weekly_data = []
    
    for i in range(6, -1, -1):  # Son 7 gün (6 gün önce -> bugün)
        target_date = today - timedelta(days=i)
        day_name = day_names_tr[target_date.weekday()]
        weekly_labels.append(f"{day_name} ({target_date.day}/{target_date.month})")
        
        # O gündeki randevu sayısı
        count = sum(1 for apt in processed_appointments if apt['date'] == target_date)
        weekly_data.append(count)
    
    # === MONTHLY TREND (Son 12 ay) ===
    month_names_tr = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 
                      'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara']
    monthly_trend_labels = []
    monthly_trend_data = []
    
    current_month = today.month
    current_year_val = today.year
    
    for i in range(11, -1, -1):  # Son 12 ay
        # Ay hesaplama
        month = current_month - i
        year = current_year_val
        
        while month <= 0:
            month += 12
            year -= 1
        
        monthly_trend_labels.append(f"{month_names_tr[month-1]} {year}")
        
        # O aydaki randevu sayısı
        count = sum(1 for apt in processed_appointments 
                   if apt['date'].month == month and apt['date'].year == year)
        monthly_trend_data.append(count)
    
    # === STATUS DISTRIBUTION (Durum dağılımı) ===
    status_labels = ['Tamamlanan', 'Planlanan', 'Bekleyen', 'İptal']
    status_data = [completed_appointments, scheduled_appointments, 
                   pending_appointments, cancelled_appointments]
    status_colors = ['#10B981', '#3B82F6', '#F59E0B', '#EF4444']
    
    # Current year statistics (mevcut kod)
    current_year = datetime.now().year
    yearly_appointments = [
        apt for apt in processed_appointments
        if apt['date'].year == current_year
    ]
    
    # Monthly distribution (mevcut kod)
    monthly_stats = defaultdict(int)
    for apt in yearly_appointments:
        monthly_stats[apt['date'].month] += 1
    
    # Chart data (mevcut kod)
    monthly_labels = [f'{month}.Ay' for month in sorted(monthly_stats.keys())]
    monthly_data = [monthly_stats[month] for month in sorted(monthly_stats.keys())]
    
    # Busiest days
    busiest_days = []
    day_counts = defaultdict(int)
    for apt in processed_appointments:
        day_counts[apt['date']] += 1
    
    sorted_days = sorted(day_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    for day, count in sorted_days:
        busiest_days.append((day.strftime('%d.%m.%Y'), count))
    
    # Busiest hours
    busiest_hours = []
    hour_counts = defaultdict(int)
    for apt in processed_appointments:
        if apt['time']:
            hour = apt['time'].hour
            hour_counts[hour] += 1
    
    sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    for hour, count in sorted_hours:
        busiest_hours.append((f'{hour:02d}:00', count))
    
    # Completion rate
    completion_rate = round((completed_appointments / total_appointments * 100), 1) if total_appointments > 0 else 0
    
    stats = {
        'total_appointments': total_appointments,
        'completed_appointments': completed_appointments,
        'scheduled_appointments': scheduled_appointments,
        'pending_appointments': pending_appointments,
        'cancelled_appointments': cancelled_appointments,
        'completion_rate': completion_rate,
        'busiest_days': busiest_days,
        'busiest_hours': busiest_hours
    }
    
    return render_template('dashboard/stats.html',
                         stats=stats,
                         # Haftalık trend
                         weekly_labels=weekly_labels,
                         weekly_data=weekly_data,
                         # Aylık trend
                         monthly_trend_labels=monthly_trend_labels,
                         monthly_trend_data=monthly_trend_data,
                         # Durum dağılımı
                         status_labels=status_labels,
                         status_data=status_data,
                         status_colors=status_colors,
                         # Mevcut veriler
                         monthly_labels=monthly_labels,
                         monthly_data=monthly_data,
                         current_year=current_year,
                         date_util=date)

@dashboard_bp.route('/blocked-days')
def blocked_days():
    """Bloklanmış günler sayfası"""
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    
    user_id = str(session.get('user_id'))
    
    # Get all blocked days
    all_blocked_data = get_data('blocked_days') or {}
    
    # Handle both dict and list (Firebase returns list for sequential integer keys)
    if isinstance(all_blocked_data, list):
        # Convert list to dict with index as key, filter None values
        all_blocked_data = {str(i): v for i, v in enumerate(all_blocked_data) if v is not None}
    
    user_blocked_days = [
        bd for bd in all_blocked_data.values()
        if bd and str(bd.get('user_id')) == str(user_id)
    ]
    
    # Process and categorize blocked days
    past_blocked = []
    today_blocked = []
    future_blocked = []
    today = date.today()
    
    for bd in user_blocked_days:
        try:
            bd_date = parse_date(bd.get('date'))
            if bd_date is None:
                continue
            
            # Create blocked day object
            bd_obj = {
                'id': bd.get('id'),
                'date': bd_date,
                'reason': bd.get('reason', ''),
                'created_at': bd.get('created_at'),
            }
            
            if bd_date < today:
                past_blocked.append(bd_obj)
            elif bd_date == today:
                today_blocked.append(bd_obj)
            else:
                future_blocked.append(bd_obj)
        except Exception as e:
            continue
    
    # Sort by date
    past_blocked.sort(key=lambda x: x['date'], reverse=True)
    today_blocked.sort(key=lambda x: x['date'])
    future_blocked.sort(key=lambda x: x['date'])
    
    from flask_wtf.csrf import generate_csrf
    return render_template('dashboard/blocked_days.html',
                         past_blocked=past_blocked,
                         today_blocked=today_blocked,
                         future_blocked=future_blocked,
                         date_util=date,
                         csrf_token=generate_csrf)

@dashboard_bp.route('/blocked-days/add', methods=['POST'])
def add_blocked_day():
    """Bloklanmış gün ekle"""
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    
    user_id = str(session.get('user_id'))
    blocked_date = request.form.get('blocked_date')
    reason = request.form.get('reason', '').strip()
    
    if not blocked_date:
        flash('Lütfen bir tarih seçin!', 'error')
        return redirect(url_for('dashboard.blocked_days'))
    
    try:
        # Parse and validate date
        blocked_date_obj = datetime.strptime(blocked_date, '%Y-%m-%d').date()
        
        # Check for past date
        if blocked_date_obj < date.today():
            flash('Geçmiş tarihleri bloklayamazsınız!', 'error')
            return redirect(url_for('dashboard.blocked_days'))
        
        # Check if already blocked
        all_blocked_data = get_data('blocked_days') or {}
        
        # Handle both dict and list
        if isinstance(all_blocked_data, list):
            all_blocked_data = {str(i): v for i, v in enumerate(all_blocked_data) if v is not None}
        
        date_str = blocked_date_obj.strftime('%Y-%m-%d')
        
        for bd in all_blocked_data.values():
            if not bd:
                continue
            if bd.get('date') == date_str and str(bd.get('user_id')) == str(user_id):
                flash('Bu tarih zaten bloklanmış!', 'error')
                return redirect(url_for('dashboard.blocked_days'))
        
        # Create new blocked day
        new_id = max([int(k) for k in all_blocked_data.keys() if str(k).isdigit()], default=0) + 1
        
        new_blocked_day = {
            'id': new_id,
            'user_id': str(user_id),
            'date': date_str,
            'reason': reason if reason else None,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
        }
        
        # Save to Firebase
        set_data(f'blocked_days/{new_id}', new_blocked_day)
        
        flash(f'{blocked_date_obj.strftime("%d.%m.%Y")} tarihi başarıyla bloklandı!', 'success')
        
    except ValueError as e:
        flash('Geçersiz tarih formatı!', 'error')
    except Exception as e:
        flash(f'Hata oluştu: {str(e)}', 'error')
    
    return redirect(url_for('dashboard.blocked_days'))

@dashboard_bp.route('/blocked-days/remove/<blocked_day_id>', methods=['POST'])
def remove_blocked_day(blocked_day_id):
    """Bloklanmış günü kaldır"""
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    
    user_id = str(session.get('user_id'))
    
    # Get blocked day
    all_blocked_data = get_data('blocked_days') or {}
    
    # Handle both dict and list
    if isinstance(all_blocked_data, list):
        all_blocked_data = {str(i): v for i, v in enumerate(all_blocked_data) if v is not None}
    
    blocked_day = all_blocked_data.get(str(blocked_day_id))
    
    if not blocked_day or (str(blocked_day.get('user_id')) != str(user_id)):
        flash('Bloklanmış gün bulunamadı!', 'error')
        return redirect(url_for('dashboard.blocked_days'))
    
    try:
        blocked_date_str = blocked_day.get('date')
        
        # Delete from Firebase
        delete_data(f'blocked_days/{blocked_day_id}')
        
        # Parse and format date for message
        try:
            blocked_date_obj = datetime.strptime(blocked_date_str, '%Y-%m-%d').date()
            date_str = blocked_date_obj.strftime('%d.%m.%Y')
        except:
            date_str = blocked_date_str
        
        flash(f'{date_str} tarihi bloklaması kaldırıldı!', 'success')
        
    except Exception as e:
        flash(f'Hata oluştu: {str(e)}', 'error')
    
    return redirect(url_for('dashboard.blocked_days'))

@dashboard_bp.route('/appointment/<int:appointment_id>')
def view(appointment_id):
    """Randevuyu görüntüle"""
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    
    user_id = str(session.get('user_id'))
    
    # Get appointment from Firebase
    all_appointments_data = get_data('appointments') or {}
    appointment = all_appointments_data.get(str(appointment_id))
    
    if not appointment or (str(appointment.get('user_id')) != str(user_id)):
        flash('Randevu bulunamadı!', 'error')
        return redirect(url_for('dashboard.appointments'))
    
    try:
        apt_date = parse_date(appointment.get('appointment_date'))
        apt_time = parse_time(appointment.get('appointment_time'))
        
        appointment_obj = {
            'id': appointment.get('id'),
            'title': appointment.get('title', 'Untitled'),
            'description': appointment.get('description', ''),
            'appointment_date': apt_date,
            'appointment_time': apt_time,
            'duration': appointment.get('duration', 60),
            'status': appointment.get('status', 'scheduled'),
            'location': appointment.get('location', ''),
            'notes': appointment.get('notes', ''),
            'created_at': appointment.get('created_at'),
            'updated_at': appointment.get('updated_at'),
        }
        
        from flask_wtf.csrf import generate_csrf
        return render_template('appointments/view.html',
                             appointment=appointment_obj,
                             date_util=date,
                             csrf_token=generate_csrf,
                             get_status_badge_class=get_status_badge_class,
                             get_status_text=get_status_text)
    except Exception as e:
        flash(f'Hata oluştu: {str(e)}', 'error')
        return redirect(url_for('dashboard.appointments'))

@dashboard_bp.route('/appointment/<int:appointment_id>/edit', methods=['GET', 'POST'])
def edit(appointment_id):
    """Randevuyu düzenle"""
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    
    user_id = str(session.get('user_id'))
    
    # Get appointment from Firebase
    all_appointments_data = get_data('appointments') or {}
    appointment = all_appointments_data.get(str(appointment_id))
    
    if not appointment or (str(appointment.get('user_id')) != str(user_id)):
        flash('Randevu bulunamadı!', 'error')
        return redirect(url_for('dashboard.appointments'))
    
    if request.method == 'POST':
        try:
            # Get form data
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            appointment_date = request.form.get('appointment_date')
            appointment_time = request.form.get('appointment_time')
            duration = request.form.get('duration', '60')
            location = request.form.get('location', '').strip()
            notes = request.form.get('notes', '').strip()
            status = request.form.get('status', '').strip()
            
            # Validate
            if not title or not appointment_date or not appointment_time:
                flash('Lütfen tüm zorunlu alanları doldurun!', 'error')
            else:
                # Parse and validate date/time
                apt_date = datetime.strptime(appointment_date, '%Y-%m-%d').date()
                apt_time = datetime.strptime(appointment_time, '%H:%M').time()
                
                if apt_date < date.today():
                    flash('Geçmiş tarihleri seçemezsiniz!', 'error')
                else:
                    # Check if date is blocked
                    all_blocked_data = get_data('blocked_days') or {}
                    date_str = apt_date.strftime('%Y-%m-%d')
                    
                    is_blocked = False
                    for bd in all_blocked_data.values():
                        if bd.get('date') == date_str and str(bd.get('user_id')) == str(user_id):
                            is_blocked = True
                            break
                    
                    if is_blocked:
                        flash('Bu tarih bloklanmış!', 'error')
                    else:
                        # Update appointment
                        updated_appointment = {
                            'id': appointment.get('id'),
                            'user_id': str(user_id),
                            'title': title,
                            'description': description,
                            'appointment_date': apt_date.strftime('%Y-%m-%d'),
                            'appointment_time': apt_time.strftime('%H:%M'),
                            'duration': int(duration) if str(duration).isdigit() else 60,
                            'location': location if location else None,
                            'notes': notes if notes else None,
                            'status': status if status else appointment.get('status', 'scheduled'),
                            'created_at': appointment.get('created_at'),
                            'updated_at': datetime.now().isoformat(),
                        }
                        
                        # Save to Firebase
                        set_data(f'appointments/{appointment_id}', updated_appointment)
                        
                        flash('Randevu başarıyla güncellendi!', 'success')
                        return redirect(url_for('dashboard.view', appointment_id=appointment_id))
        
        except ValueError as e:
            flash('Geçersiz tarih veya saat formatı!', 'error')
        except Exception as e:
            flash(f'Hata oluştu: {str(e)}', 'error')
    
    try:
        # Prepare appointment data for display
        apt_date = parse_date(appointment.get('appointment_date'))
        apt_time = parse_time(appointment.get('appointment_time'))
        
        # Güvenli strftime: apt_date ve apt_time nesne mi kontrolü
        if isinstance(apt_date, str):
            apt_date_str = apt_date
        elif apt_date:
            apt_date_str = apt_date.strftime('%Y-%m-%d')
        else:
            apt_date_str = ''

        if isinstance(apt_time, str):
            apt_time_str = apt_time
        elif apt_time:
            apt_time_str = apt_time.strftime('%H:%M')
        else:
            apt_time_str = ''

        appointment_obj = {
            'id': appointment.get('id'),
            'title': appointment.get('title', ''),
            'description': appointment.get('description', ''),
            'appointment_date': apt_date,
            'appointment_date_str': apt_date_str,
            'appointment_time': apt_time,
            'appointment_time_str': apt_time_str,
            'duration': appointment.get('duration', 60),
            'location': appointment.get('location', ''),
            'notes': appointment.get('notes', ''),
            'status': appointment.get('status', 'scheduled'),
        }
        
        from flask_wtf.csrf import generate_csrf
        return render_template('appointments/edit.html',
                             appointment=appointment_obj,
                             date_util=date,
                             csrf_token=generate_csrf)
    except Exception as e:
        flash(f'Hata oluştu: {str(e)}', 'error')
        return redirect(url_for('dashboard.appointments'))

@dashboard_bp.route('/blocked-days/check')
def check_blocked_date():
    """Tarih bloklanmış mı kontrol et (AJAX)"""
    if not session.get('user_id'):
        return jsonify({'blocked': False})
    
    user_id = str(session.get('user_id'))
    check_date = request.args.get('date')
    
    if not check_date:
        return jsonify({'blocked': False})
    
    try:
        check_date_obj = datetime.strptime(check_date, '%Y-%m-%d').date()
        date_str = check_date_obj.strftime('%Y-%m-%d')
        
        # Get blocked days
        all_blocked_data = get_data('blocked_days') or {}
        
        for bd in all_blocked_data.values():
            if bd.get('date') == date_str and str(bd.get('user_id')) == str(user_id):
                return jsonify({'blocked': True})
        
        return jsonify({'blocked': False})
    except ValueError:
        return jsonify({'blocked': False})

@dashboard_bp.route('/appointments/<appointment_id>/approve', methods=['POST'])
def approve_appointment(appointment_id):
    """Randevuyu onayla"""
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    appointments = get_data('appointments') or {}
    appointment = appointments.get(appointment_id)
    if appointment:
        appointment['status'] = 'approved'
        set_data(f'appointments/{appointment_id}', appointment)
        flash('Randevu onaylandı.', 'success')
    else:
        flash('Randevu bulunamadı.', 'danger')
    return redirect(url_for('dashboard.dashboard'))

@dashboard_bp.route('/appointments/<appointment_id>/reject', methods=['POST'])
def reject_appointment(appointment_id):
    """Randevuyu reddet"""
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    appointments = get_data('appointments') or {}
    appointment = appointments.get(appointment_id)
    if appointment:
        appointment['status'] = 'rejected'
        set_data(f'appointments/{appointment_id}', appointment)
        flash('Randevu reddedildi.', 'warning')
    else:
        flash('Randevu bulunamadı.', 'danger')
    return redirect(url_for('dashboard.dashboard'))

from flask import g
from services.auth_service import token_required

@dashboard_bp.route('/api/me')
@token_required
def get_me():
    """
    A protected test endpoint to get the current user's info from the token.
    """
    # The g.current_user is set by the @token_required decorator
    user_info = g.current_user
    
    # You can enrich this with data from your own database if needed
    # For example: user_profile = get_data(f"users/{user_info['uid']}")
    
    return jsonify({
        "uid": user_info.get('uid'),
        "email": user_info.get('email'),
        "name": user_info.get('name'),
        "picture": user_info.get('picture'),
        "email_verified": user_info.get('email_verified')
    })
