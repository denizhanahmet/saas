
from datetime import date, datetime, time, timedelta
import threading
import uuid

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_mail import Message
from flask_wtf.csrf import generate_csrf

# Firebase Realtime Database integration
from firebase_realtime import get_data, set_data, delete_data, update_data
from services.sms_service import get_sms_service

appointments_bp = Blueprint('appointments', __name__)

def send_async_email(app, msg):
    with app.app_context():
        try:
            app.extensions['mail'].send(msg)
        except Exception as e:
            print(f"Mail sending error: {e}")

# Randevu durumunu güncelle (tamamlandı/iptal)
@appointments_bp.route('/update-status/<int:appointment_id>', methods=['POST'])
def update_status(appointment_id):
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))

    user_id = str(session.get('user_id'))
    all_appointments_data = get_data('appointments') or {}
    appointment = all_appointments_data.get(str(appointment_id))

    if not appointment or (str(appointment.get('user_id')) != str(user_id)):
        flash('Randevu bulunamadı!', 'error')
        return redirect(url_for('dashboard.appointments'))

    status = request.form.get('status')
    if status not in ['completed', 'cancelled']:
        flash('Geçersiz durum!', 'error')
        return redirect(url_for('dashboard.view', appointment_id=appointment_id))

    try:
        appointment['status'] = status
        appointment['updated_at'] = datetime.now().isoformat()
        set_data(f'appointments/{appointment_id}', appointment)
        flash('Randevu durumu güncellendi.', 'success')
    except Exception as e:
        flash(f'Hata oluştu: {str(e)}', 'error')

    return redirect(url_for('dashboard.view', appointment_id=appointment_id))

# Helper functions
def parse_date(date_str):
    """Convert date string (YYYY-MM-DD) to date object"""
    if isinstance(date_str, str):
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return None
    return date_str

def parse_time(time_str):
    """Convert time string (HH:MM) to time object"""
    if isinstance(time_str, str):
        try:
            return datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            return None
    return time_str

def is_date_blocked(user_id, check_date):
    """Check if date is blocked for user"""
    all_blocked_data = get_data('blocked_days') or {}
    date_str = check_date.strftime('%Y-%m-%d') if isinstance(check_date, date) else check_date
    
    for bd in all_blocked_data.values():
        if bd.get('date') == date_str and str(bd.get('user_id')) == str(user_id):
            return True
    return False

def has_time_conflict(user_id, appointment_date, appointment_time, duration, exclude_id=None):
    """Check if appointment time conflicts with existing appointments"""
    all_appointments_data = get_data('appointments') or {}
    
    for apt_id, apt in all_appointments_data.items():
        if exclude_id and str(apt_id) == str(exclude_id):
            continue
        
        if str(apt.get('user_id')) != str(user_id):
            continue
        
        if apt.get('status') == 'cancelled':
            continue
        
        apt_date = parse_date(apt.get('appointment_date'))
        apt_time = parse_time(apt.get('appointment_time'))
        apt_duration = apt.get('duration', 60)
        
        if apt_date != appointment_date:
            continue
        
        if apt_time is None or appointment_time is None:
            continue
        
        # Check time conflict
        apt_end = datetime.combine(date.today(), apt_time)
        apt_end = apt_end.replace(hour=apt_time.hour, minute=apt_time.minute)
        apt_end_minutes = apt_time.hour * 60 + apt_time.minute + apt_duration
        
        new_start_minutes = appointment_time.hour * 60 + appointment_time.minute
        new_end_minutes = new_start_minutes + duration
        
        apt_start_minutes = apt_time.hour * 60 + apt_time.minute
        
        # Check if times overlap
        if not (new_end_minutes <= apt_start_minutes or new_start_minutes >= apt_end_minutes):
            return True
    
    return False

# Eğitmen panelinde bekleyen randevular
@appointments_bp.route('/pending')
def pending_appointments():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    
    user_id = str(session.get('user_id'))
    
    # Get all pending appointments for this user
    all_appointments_data = get_data('appointments') or {}
    pending = []
    
    for apt_id, apt in all_appointments_data.items():
        if str(apt.get('user_id')) == str(user_id):
            if apt.get('status') == 'pending':
                apt_date = parse_date(apt.get('appointment_date'))
                apt_time = parse_time(apt.get('appointment_time'))
                
                if apt_date is not None and apt_time is not None:
                    pending.append({
                        'id': apt.get('id'),
                        'title': apt.get('title', 'Untitled'),
                        'description': apt.get('description', ''),
                        'appointment_date': apt_date,
                        'appointment_time': apt_time,
                        'duration': apt.get('duration', 60),
                        'location': apt.get('location', ''),
                        'notes': apt.get('notes', ''),
                    })
    
    # Sort by date and time
    pending.sort(key=lambda x: (x['appointment_date'], x['appointment_time']))
    
    return render_template('appointments/pending.html', appointments=pending)

# Randevu onay/red işlemleri
@appointments_bp.route('/approve/<int:appointment_id>', methods=['POST'])
def approve_appointment(appointment_id):
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    
    user_id = str(session.get('user_id'))
    
    # Get appointment from Firebase
    all_appointments_data = get_data('appointments') or {}
    appointment = all_appointments_data.get(str(appointment_id))
    
    if not appointment or (str(appointment.get('user_id')) != str(user_id)):
        flash('Randevu bulunamadı!', 'error')
        return redirect(url_for('appointments.pending_appointments'))
    
    try:
        # Update appointment status
        appointment['status'] = 'scheduled'
        appointment['updated_at'] = datetime.now().isoformat()
        set_data(f'appointments/{appointment_id}', appointment)
        
        # Müşteriye onay SMS'i gönder
        client_phone = appointment.get('client_phone')
        # Eski kayıtlar için notlardan telefon bulmaya çalış
        if not client_phone and appointment.get('notes'):
            import re
            match = re.search(r'Telefon: ([\d\+\s]+)', appointment['notes'])
            if match:
                client_phone = match.group(1).strip()
                
        if client_phone:
            sms_service = get_sms_service()
            appt_date = appointment.get('appointment_date')
            appt_time = appointment.get('appointment_time')
            msg = f"Sayın {appointment.get('client_name', 'Müşteri')}, {appt_date} saat {appt_time} randevunuz onaylanmıştır."
            sms_service.send_sms(client_phone, msg, user_id)
            
        # Müşteriye onay E-postası gönder
        client_email = appointment.get('client_email')
        if client_email:
            try:
                users = get_data('users') or {}
                instructor = users.get(user_id, {})
                company_name = instructor.get('company_name') or f"{instructor.get('first_name', '')} {instructor.get('last_name', '')}".strip() or "Randevu Sistemi"
                
                subject = f"Randevunuz Onaylandı - {company_name}"
                body = f"""Sayın {appointment.get('client_name', 'Müşteri')},

{appointment.get('appointment_date')} tarihinde saat {appointment.get('appointment_time')} için oluşturduğunuz randevu talebiniz onaylanmıştır.

Teşekkürler,
{company_name}"""
                msg = Message(subject, recipients=[client_email], body=body)
                threading.Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start()
            except Exception as e:
                print(f"Email error: {e}")
        
        flash('Randevu onaylandı.', 'success')
    except Exception as e:
        flash(f'Hata oluştu: {str(e)}', 'error')
    
    return redirect(request.referrer or url_for('dashboard.appointments'))

@appointments_bp.route('/reject/<int:appointment_id>', methods=['POST'])
def reject_appointment(appointment_id):
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    
    user_id = str(session.get('user_id'))
    
    # Get appointment from Firebase
    all_appointments_data = get_data('appointments') or {}
    appointment = all_appointments_data.get(str(appointment_id))
    
    if not appointment or (str(appointment.get('user_id')) != str(user_id)):
        flash('Randevu bulunamadı!', 'error')
        return redirect(url_for('appointments.pending_appointments'))
    
    try:
        # Update appointment status
        appointment['status'] = 'rejected'
        appointment['updated_at'] = datetime.now().isoformat()
        set_data(f'appointments/{appointment_id}', appointment)
        
        # Müşteriye ret SMS'i gönder
        client_phone = appointment.get('client_phone')
        if not client_phone and appointment.get('notes'):
            import re
            match = re.search(r'Telefon: ([\d\+\s]+)', appointment['notes'])
            if match:
                client_phone = match.group(1).strip()
                
        if client_phone:
            sms_service = get_sms_service()
            msg = f"Sayın {appointment.get('client_name', 'Müşteri')}, randevu talebiniz maalesef onaylanamamıştır."
            sms_service.send_sms(client_phone, msg, user_id)
            
        # Müşteriye ret E-postası gönder
        client_email = appointment.get('client_email')
        if client_email:
            try:
                users = get_data('users') or {}
                instructor = users.get(user_id, {})
                company_name = instructor.get('company_name') or f"{instructor.get('first_name', '')} {instructor.get('last_name', '')}".strip() or "Randevu Sistemi"
                
                subject = f"Randevu Talebiniz Hakkında - {company_name}"
                body = f"""Sayın {appointment.get('client_name', 'Müşteri')},

{appointment.get('appointment_date')} tarihinde saat {appointment.get('appointment_time')} için oluşturduğunuz randevu talebiniz maalesef onaylanamamıştır.

Anlayışınız için teşekkür ederiz.

Saygılarımızla,
{company_name}"""
                msg = Message(subject, recipients=[client_email], body=body)
                threading.Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start()
            except Exception as e:
                print(f"Email error: {e}")
        
        flash('Randevu reddedildi.', 'info')
    except Exception as e:
        flash(f'Hata oluştu: {str(e)}', 'error')
    
    return redirect(request.referrer or url_for('dashboard.appointments'))

# --- Öğrenci randevu talep formu (kayıtsız) ---
@appointments_bp.route('/r/<unique_link>', methods=['GET', 'POST'])
def public_appointment_request(unique_link):
    """Public appointment request form using unique instructor link"""
    # Get instructor by unique_link from Firebase
    all_users_data = get_data('users') or {}
    instructor = None
    instructor_id = None
    
    for uid, user_data in all_users_data.items():
        if user_data.get('unique_link') == unique_link:
            instructor = user_data
            instructor_id = uid
            break
    
    if not instructor:
        abort(404)
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        appointment_date = request.form.get('appointment_date')
        appointment_time = request.form.get('appointment_time')
        note = request.form.get('note', '').strip()
        
        # Validate
        import re
        email_regex = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        phone_regex = r"^(\+90|0)?5\d{9}$"
        errors = []
        if not name or len(name) < 3:
            errors.append('Ad soyad en az 3 karakter olmalı.')
        if not phone or not re.match(phone_regex, phone):
            errors.append('Geçerli bir Türk GSM numarası giriniz. (05XXXXXXXXX veya +905XXXXXXXXX)')
        if email and not re.match(email_regex, email):
            errors.append('Geçerli bir email adresi giriniz.')
        if not appointment_date:
            errors.append('Tarih seçilmelidir.')
        if not appointment_time:
            errors.append('Saat seçilmelidir.')

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('public_appointment_form.html', user=instructor, csrf_token=generate_csrf())
        
        # Güvenli ve açıklayıcı validasyon
        if not appointment_date or not appointment_time:
            flash('Tarih ve saat alanları zorunludur.', 'error')
            return render_template('public_appointment_form.html', user=instructor, csrf_token=generate_csrf())
        try:
            appt_date_obj = datetime.strptime(appointment_date, '%Y-%m-%d').date()
        except ValueError:
            flash('Tarih formatı geçersiz. Lütfen YYYY-AA-GG şeklinde girin.', 'error')
            return render_template('public_appointment_form.html', user=instructor, csrf_token=generate_csrf())
        try:
            appt_time_obj = datetime.strptime(appointment_time, '%H:%M').time()
        except ValueError:
            flash('Saat formatı geçersiz. Lütfen SS:dd şeklinde girin.', 'error')
            return render_template('public_appointment_form.html', user=instructor, csrf_token=generate_csrf())

        try:
            # Check if date is blocked
            if is_date_blocked(instructor_id, appt_date_obj):
                flash('Seçilen tarih bloklanmış! Bu tarihte randevu alınamaz.', 'error')
                return render_template('public_appointment_form.html', user=instructor, csrf_token=generate_csrf())
            # Check for time conflicts
            if has_time_conflict(instructor_id, appt_date_obj, appt_time_obj, 60):
                flash('Bu saatte zaten bir randevu var!', 'error')
                return render_template('public_appointment_form.html', user=instructor, csrf_token=generate_csrf())
            # Create new appointment
            all_appointments_data = get_data('appointments') or {}
            new_id = max([int(k) for k in all_appointments_data.keys() if str(k).isdigit()], default=0) + 1
            new_appointment = {
                'id': new_id,
                'user_id': str(instructor_id),
                'title': f"{name} - Randevu Talebi",
                'description': note if note else None,
                'appointment_date': appt_date_obj.strftime('%Y-%m-%d'),
                'appointment_time': appt_time_obj.strftime('%H:%M'),
                'duration': 60,
                'status': 'pending',
                'client_name': name,
                'client_phone': phone,
                'client_email': email,
                'location': '',
                'notes': f'Telefon: {phone}\nEmail: {email}',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
            }
            set_data(f'appointments/{new_id}', new_appointment)
            flash('Randevu isteğiniz alınmıştır, eğitmeniniz onayladığında size geri dönüş yapılacaktır.', 'success')
            return redirect(url_for('appointments.public_appointment_request', unique_link=unique_link))
        except Exception as e:
            flash(f'Bir hata oluştu, lütfen tekrar deneyin: {str(e)}', 'error')
            return render_template('public_appointment_form.html', user=instructor, csrf_token=generate_csrf())
    
    return render_template('public_appointment_form.html', user=instructor, csrf_token=generate_csrf())

@appointments_bp.route('/create', methods=['GET', 'POST'])
def create():
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    
    """Yeni randevu oluştur"""
    user_id = str(session.get('user_id'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        appointment_date = request.form.get('appointment_date')
        appointment_time = request.form.get('appointment_time')
        duration = request.form.get('duration', '60')
        location = request.form.get('location', '').strip()
        notes = request.form.get('notes', '').strip()
        
        # Validasyonlar
        import re
        email_regex = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        phone_regex = r"^(\+90|0)?5\d{9}$"
        errors = []

        if not title or len(title) < 3:
            errors.append('Randevu başlığı en az 3 karakter olmalıdır.')

        # Notlar alanında email ve telefon varsa kontrol et
        if notes:
            for match in re.findall(r"[\w\.-]+@[\w\.-]+", notes):
                if not re.match(email_regex, match):
                    errors.append('Notlar alanında geçersiz email adresi var.')
            for match in re.findall(r"(\+90|0)?5\d{9}", notes):
                if not re.match(phone_regex, match):
                    errors.append('Notlar alanında geçersiz Türk GSM numarası var.')

        if not appointment_date:
            errors.append('Tarih seçilmelidir.')
        else:
            try:
                appt_date_obj = datetime.strptime(appointment_date, '%Y-%m-%d').date()
                if appt_date_obj < date.today():
                    errors.append('Geçmiş tarihli randevu oluşturulamaz.')
            except ValueError:
                errors.append('Geçersiz tarih formatı.')
                appt_date_obj = None

        if not appointment_time:
            errors.append('Saat seçilmelidir.')
        else:
            try:
                appt_time_obj = datetime.strptime(appointment_time, '%H:%M').time()
            except ValueError:
                errors.append('Geçersiz saat formatı.')
                appt_time_obj = None

        try:
            duration_int = int(duration)
            if duration_int < 15 or duration_int > 480:  # 15 dakika - 8 saat
                errors.append('Süre 15 dakika ile 8 saat arasında olmalıdır.')
        except ValueError:
            errors.append('Geçersiz süre değeri.')
            duration_int = 60

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('appointments/create.html', date=date)
        
        try:
            # Check if date is blocked
            if is_date_blocked(user_id, appt_date_obj):
                flash('Seçilen tarih bloklanmış! Bu tarihte randevu alınamaz.', 'error')
                return render_template('appointments/create.html', date=date)
            
            # Check for time conflicts
            if has_time_conflict(user_id, appt_date_obj, appt_time_obj, duration_int):
                flash('Bu saatte zaten bir randevunuz var!', 'error')
                return render_template('appointments/create.html', date=date)
            
            # Create new appointment
            all_appointments_data = get_data('appointments') or {}
            new_id = max([int(k) for k in all_appointments_data.keys() if str(k).isdigit()], default=0) + 1
            new_appointment = {
                'id': new_id,
                'user_id': str(user_id),
                'title': title,
                'description': description if description else None,
                'appointment_date': appt_date_obj.strftime('%Y-%m-%d'),
                'appointment_time': appt_time_obj.strftime('%H:%M'),
                'duration': duration_int,
                'status': 'scheduled',
                'location': location if location else None,
                'notes': notes if notes else None,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
            }
            
            set_data(f'appointments/{new_id}', new_appointment)
            
            flash('Randevu başarıyla oluşturuldu!', 'success')
            return redirect(url_for('dashboard.appointments'))
        
        except Exception as e:
            flash(f'Randevu oluşturulurken bir hata oluştu: {str(e)}', 'error')
    
    return render_template('appointments/create.html', date=date)


# Remaining endpoints delegated to dashboard.py for appointment management
# The view(), edit(), and delete() are handled by dashboard.view(), dashboard.edit()

@appointments_bp.route('/api/check-conflict', methods=['POST'])
def check_conflict():
    """AJAX time conflict check"""
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = str(session.get('user_id'))
    data = request.get_json()
    
    try:
        appointment_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        appointment_time = datetime.strptime(data['time'], '%H:%M').time()
        duration = int(data['duration'])
        exclude_id = data.get('exclude_id')  # Exclude current appointment during edit
        
        # Check for time conflicts
        has_conflict = has_time_conflict(user_id, appointment_date, appointment_time, duration, exclude_id)
        
        return jsonify({
            'has_conflict': has_conflict,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400
