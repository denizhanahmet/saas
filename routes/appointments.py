
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from datetime import datetime, date, time, timedelta
from werkzeug.exceptions import abort
from models import Appointment, BlockedDay, db, SmsLog, Client, User
from sqlalchemy import func, and_, or_
from flask_wtf.csrf import generate_csrf

appointments_bp = Blueprint('appointments', __name__)

# Eğitmen panelinde bekleyen randevular
@appointments_bp.route('/pending')
@login_required
def pending_appointments():
    appointments = Appointment.query.filter_by(user_id=current_user.id, status='pending').order_by(Appointment.appointment_date.asc(), Appointment.appointment_time.asc()).all()
    return render_template('appointments/pending.html', appointments=appointments)

# Randevu onay/red işlemleri
@appointments_bp.route('/approve/<int:appointment_id>', methods=['POST'])
@login_required
def approve_appointment(appointment_id):
    appointment = Appointment.query.filter_by(id=appointment_id, user_id=current_user.id).first_or_404()
    appointment.status = 'scheduled'
    db.session.commit()
    flash('Randevu onaylandı.', 'success')
    return redirect(url_for('appointments.pending_appointments'))

@appointments_bp.route('/reject/<int:appointment_id>', methods=['POST'])
@login_required
def reject_appointment(appointment_id):
    appointment = Appointment.query.filter_by(id=appointment_id, user_id=current_user.id).first_or_404()
    appointment.status = 'rejected'
    db.session.commit()
    flash('Randevu reddedildi.', 'info')
    return redirect(url_for('appointments.pending_appointments'))

# --- Öğrenci randevu talep formu (kayıtsız) ---
@appointments_bp.route('/r/<unique_link>', methods=['GET', 'POST'])
def public_appointment_request(unique_link):
    # Eğitmeni bul
    user = User.query.filter_by(unique_link=unique_link).first()
    if not user:
        abort(404)

    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        appointment_date = request.form.get('appointment_date')
        appointment_time = request.form.get('appointment_time')
        note = request.form.get('note')

        errors = []
        if not name or len(name.strip()) < 3:
            errors.append('Ad soyad en az 3 karakter olmalı.')
        if not phone or len(phone) < 8:
            errors.append('Telefon geçersiz.')
        if not appointment_date:
            errors.append('Tarih seçilmelidir.')
        if not appointment_time:
            errors.append('Saat seçilmelidir.')

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('public_appointment_form.html', user=user, csrf_token=generate_csrf())

        # Appointment kaydı
        try:
            appointment = Appointment(
                user_id=user.id,
                title=f"{name} - Online Randevu",
                description=note,
                appointment_date=datetime.strptime(appointment_date, '%Y-%m-%d').date(),
                appointment_time=datetime.strptime(appointment_time, '%H:%M').time(),
                duration=60,
                status='pending',
                location='',
                notes='',
            )
            db.session.add(appointment)
            db.session.commit()
            flash('Randevu isteğiniz alınmıştır, eğitmeniniz onayladığında size geri dönüş yapılacaktır.', 'success')
            return redirect(url_for('appointments.public_appointment_request', unique_link=unique_link))
        except Exception as e:
            db.session.rollback()
            flash('Bir hata oluştu, lütfen tekrar deneyin.', 'error')
            return render_template('public_appointment_form.html', user=user, csrf_token=generate_csrf())

    return render_template('public_appointment_form.html', user=user, csrf_token=generate_csrf())

@appointments_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Yeni randevu oluştur"""
    # importlar dosya başında
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        appointment_date = request.form.get('appointment_date')
        appointment_time = request.form.get('appointment_time')
        duration = request.form.get('duration', 60)
        location = request.form.get('location')
        notes = request.form.get('notes')
        
        # Validasyonlar
        errors = []
        
        if not title or len(title.strip()) < 3:
            errors.append('Randevu başlığı en az 3 karakter olmalıdır.')
        
        if not appointment_date:
            errors.append('Tarih seçilmelidir.')
        else:
            try:
                appointment_date = datetime.strptime(appointment_date, '%Y-%m-%d').date()
                if appointment_date < date.today():
                    errors.append('Geçmiş tarihli randevu oluşturulamaz.')
            except ValueError:
                errors.append('Geçersiz tarih formatı.')
        
        if not appointment_time:
            errors.append('Saat seçilmelidir.')
        else:
            try:
                appointment_time = datetime.strptime(appointment_time, '%H:%M').time()
            except ValueError:
                errors.append('Geçersiz saat formatı.')
        
        try:
            duration = int(duration)
            if duration < 15 or duration > 480:  # 15 dakika - 8 saat
                errors.append('Süre 15 dakika ile 8 saat arasında olmalıdır.')
        except ValueError:
            errors.append('Geçersiz süre değeri.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('appointments/create.html', date=date)
        
        # Bloklanmış gün kontrolü
    # importlar dosya başında
        if BlockedDay.is_date_blocked(current_user.id, appointment_date):
            flash('Seçilen tarih bloklanmış! Bu tarihte randevu alınamaz.', 'error')
            return render_template('appointments/create.html', date=date)
        
        # Çakışma kontrolü
        existing_appointment = Appointment.query.filter(
            Appointment.user_id == current_user.id,
            Appointment.appointment_date == appointment_date,
            Appointment.status != 'cancelled'
        ).filter(
            # Zaman çakışması kontrolü
            db.or_(
                # Yeni randevunun başlangıcı mevcut randevunun içinde
                db.and_(
                    Appointment.appointment_time <= appointment_time,
                    db.func.time(Appointment.appointment_time, f'+{duration} minutes') > appointment_time
                ),
                # Yeni randevunun bitişi mevcut randevunun içinde
                db.and_(
                    appointment_time < db.func.time(Appointment.appointment_time, f'+{Appointment.duration} minutes'),
                    db.func.time(appointment_time, f'+{duration} minutes') > Appointment.appointment_time
                )
            )
        ).first()
        
        if existing_appointment:
            flash('Bu saatte zaten bir randevunuz var!', 'error')
            return render_template('appointments/create.html', date=date)
        
        # Kendi panelinden randevu oluşturan herkes için status 'scheduled' olacak
        appointment = Appointment(
            user_id=current_user.id,
            title=title,
            description=description,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            duration=duration,
            location=location,
            notes=notes,
            status='scheduled'
        )
        
        try:
            db.session.add(appointment)
            db.session.commit()
            
            # Schedule reminder SMS (24 hours before appointment)
            try:
                from app import get_scheduler_service
                scheduler = get_scheduler_service()
                if scheduler:
                    appointment_datetime = appointment.get_datetime()
                    reminder_time = appointment_datetime - timedelta(hours=24)
                    
                    # Only schedule if reminder time is in the future
                    if reminder_time > datetime.now():
                        scheduler.schedule_appointment_reminder(appointment.id, reminder_time)
            except Exception as e:
                # Don't fail appointment creation if reminder scheduling fails
                print(f"Failed to schedule reminder: {str(e)}")
            
            flash('Randevu başarıyla oluşturuldu!', 'success')
            return redirect(url_for('dashboard.appointments'))
        except Exception as e:
            db.session.rollback()
            flash('Randevu oluşturulurken bir hata oluştu.', 'error')
    
    return render_template('appointments/create.html', date=date)

@appointments_bp.route('/<int:appointment_id>')
@login_required
def view(appointment_id):
    """Randevu detaylarını görüntüle"""
    appointment = Appointment.query.filter_by(
        id=appointment_id,
        user_id=current_user.id
    ).first_or_404()
    
    return render_template('appointments/view.html', appointment=appointment)

@appointments_bp.route('/<int:appointment_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(appointment_id):
    """Randevu düzenle"""
    appointment = Appointment.query.filter_by(
        id=appointment_id,
        user_id=current_user.id
    ).first_or_404()
    
    if request.method == 'POST':
        appointment.title = request.form.get('title', appointment.title)
        appointment.description = request.form.get('description', appointment.description)
        appointment.location = request.form.get('location', appointment.location)
        appointment.notes = request.form.get('notes', appointment.notes)
        
        # Tarih ve saat güncellemesi
        new_date = request.form.get('appointment_date')
        new_time = request.form.get('appointment_time')
        new_duration = request.form.get('duration')
        
        if new_date:
            try:
                appointment.appointment_date = datetime.strptime(new_date, '%Y-%m-%d').date()
                if appointment.appointment_date < date.today():
                    flash('Geçmiş tarihli randevu oluşturulamaz.', 'error')
                    return render_template('appointments/edit.html', appointment=appointment, date=date)
            except ValueError:
                flash('Geçersiz tarih formatı.', 'error')
                return render_template('appointments/edit.html', appointment=appointment, date=date)
        
        if new_time:
            try:
                appointment.appointment_time = datetime.strptime(new_time, '%H:%M').time()
            except ValueError:
                flash('Geçersiz saat formatı.', 'error')
                return render_template('appointments/edit.html', appointment=appointment, date=date)
        
        if new_duration:
            try:
                duration = int(new_duration)
                if 15 <= duration <= 480:
                    appointment.duration = duration
                else:
                    flash('Süre 15 dakika ile 8 saat arasında olmalıdır.', 'error')
                    return render_template('appointments/edit.html', appointment=appointment)
            except ValueError:
                flash('Geçersiz süre değeri.', 'error')
                return render_template('appointments/edit.html', appointment=appointment, date=date)
        
        try:
            db.session.commit()
            
            # Reschedule reminder SMS if appointment is still scheduled
            if appointment.status == 'scheduled':
                try:
                    from app import get_scheduler_service
                    scheduler = get_scheduler_service()
                    if scheduler:
                        appointment_datetime = appointment.get_datetime()
                        reminder_time = appointment_datetime - timedelta(hours=24)
                        
                        # Only reschedule if reminder time is in the future
                        if reminder_time > datetime.now():
                            scheduler.reschedule_appointment_reminder(appointment.id, reminder_time)
                        else:
                            # Remove reminder if it's too late
                            scheduler.remove_appointment_reminder(appointment.id)
                except Exception as e:
                    # Don't fail appointment update if reminder scheduling fails
                    print(f"Failed to reschedule reminder: {str(e)}")
            
            flash('Randevu başarıyla güncellendi!', 'success')
            return redirect(url_for('appointments.view', appointment_id=appointment.id))
        except Exception as e:
            db.session.rollback()
            flash('Randevu güncellenirken bir hata oluştu.', 'error')
    
    return render_template('appointments/edit.html', appointment=appointment, date=date)

@appointments_bp.route('/<int:appointment_id>/delete', methods=['POST'])
@login_required
def delete(appointment_id):
    """Randevu sil"""
    appointment = Appointment.query.filter_by(
        id=appointment_id,
        user_id=current_user.id
    ).first_or_404()
    
    try:
        # Remove scheduled reminder before deleting appointment
        try:
            from app import get_scheduler_service
            scheduler = get_scheduler_service()
            if scheduler:
                scheduler.remove_appointment_reminder(appointment.id)
        except Exception as e:
            # Don't fail deletion if reminder removal fails
            print(f"Failed to remove reminder: {str(e)}")
        
        db.session.delete(appointment)
        db.session.commit()
        flash('Randevu başarıyla silindi!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Randevu silinirken bir hata oluştu.', 'error')
    
    return redirect(url_for('dashboard.appointments'))

@appointments_bp.route('/<int:appointment_id>/status', methods=['POST'])
@login_required
def update_status(appointment_id):
    """Randevu durumunu güncelle"""
    appointment = Appointment.query.filter_by(
        id=appointment_id,
        user_id=current_user.id
    ).first_or_404()
    
    new_status = request.form.get('status')
    valid_statuses = ['scheduled', 'completed', 'cancelled']
    
    if new_status not in valid_statuses:
        flash('Geçersiz durum değeri.', 'error')
        return redirect(url_for('appointments.view', appointment_id=appointment.id))
    
    appointment.status = new_status
    
    try:
        db.session.commit()
        
        # Handle reminder scheduling based on status
        try:
            from app import get_scheduler_service
            scheduler = get_scheduler_service()
            if scheduler:
                if new_status == 'scheduled':
                    # Schedule reminder for newly scheduled appointment
                    appointment_datetime = appointment.get_datetime()
                    reminder_time = appointment_datetime - timedelta(hours=24)
                    
                    if reminder_time > datetime.now():
                        scheduler.schedule_appointment_reminder(appointment.id, reminder_time)
                else:
                    # Remove reminder for cancelled/completed appointments
                    scheduler.remove_appointment_reminder(appointment.id)
        except Exception as e:
            # Don't fail status update if reminder scheduling fails
            print(f"Failed to handle reminder for status change: {str(e)}")
        
        flash(f'Randevu durumu "{appointment.get_status_text()}" olarak güncellendi!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Durum güncellenirken bir hata oluştu.', 'error')
    
    return redirect(url_for('appointments.view', appointment_id=appointment.id))

@appointments_bp.route('/api/check-conflict', methods=['POST'])
@login_required
def check_conflict():
    """AJAX ile çakışma kontrolü"""
    data = request.get_json()
    
    appointment_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
    appointment_time = datetime.strptime(data['time'], '%H:%M').time()
    duration = int(data['duration'])
    exclude_id = data.get('exclude_id')  # Düzenleme sırasında mevcut randevuyu hariç tut
    
    # Çakışma kontrolü
    query = Appointment.query.filter(
        Appointment.user_id == current_user.id,
        Appointment.appointment_date == appointment_date,
        Appointment.status != 'cancelled'
    )
    
    if exclude_id:
        query = query.filter(Appointment.id != exclude_id)
    
    conflicting_appointment = query.filter(
        db.or_(
            db.and_(
                Appointment.appointment_time <= appointment_time,
                db.func.time(Appointment.appointment_time, f'+{Appointment.duration} minutes') > appointment_time
            ),
            db.and_(
                appointment_time < db.func.time(Appointment.appointment_time, f'+{Appointment.duration} minutes'),
                db.func.time(appointment_time, f'+{duration} minutes') > Appointment.appointment_time
            )
        )
    ).first()
    
    return jsonify({
        'has_conflict': conflicting_appointment is not None,
        'conflicting_appointment': {
            'title': conflicting_appointment.title,
            'time': conflicting_appointment.appointment_time.strftime('%H:%M'),
            'duration': conflicting_appointment.duration
        } if conflicting_appointment else None
    })
