"""
Waitlist Routes - Endpoints for waitlist management
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for, jsonify

from firebase_realtime import get_data, set_data, update_data
from services.waitlist_service import get_waitlist_service

logger = logging.getLogger(__name__)

waitlist_bp = Blueprint('waitlist', __name__)


# Simple in-memory rate limiter
class IPRateLimiter:
    """Simple IP-based rate limiter"""
    
    def __init__(self, max_requests: int = 10, window_seconds: int = 3600):
        self.max_requests = max_requests  # Max requests per window
        self.window_seconds = window_seconds  # Time window in seconds
        self.requests = defaultdict(list)  # IP -> list of timestamps
    
    def is_allowed(self, ip: str) -> bool:
        """Check if IP is allowed to make a request"""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window_seconds)
        
        # Clean old requests
        self.requests[ip] = [ts for ts in self.requests[ip] if ts > cutoff]
        
        # Check limit
        if len(self.requests[ip]) >= self.max_requests:
            return False
        
        # Record this request
        self.requests[ip].append(now)
        return True
    
    def get_remaining(self, ip: str) -> int:
        """Get remaining requests for IP"""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window_seconds)
        
        # Clean old requests
        self.requests[ip] = [ts for ts in self.requests[ip] if ts > cutoff]
        
        return max(0, self.max_requests - len(self.requests[ip]))


# Global rate limiter instance (10 requests per hour per IP)
waitlist_rate_limiter = IPRateLimiter(max_requests=10, window_seconds=3600)


def login_required(f):
    """Require login for waitlist routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Bu sayfaya erişmek için giriş yapmalısınız.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


@waitlist_bp.route('/')
@login_required
def waitlist_dashboard():
    """Waitlist management dashboard"""
    user_id = str(session.get('user_id'))
    
    service = get_waitlist_service(user_id)
    entries = service.get_user_waitlist()
    
    # Separate by status
    waiting = [e for e in entries if e.get('status') == 'waiting']
    notified = [e for e in entries if e.get('status') == 'notified']
    booked = [e for e in entries if e.get('status') == 'booked']
    
    return render_template('dashboard/waitlist.html',
                           waiting=waiting,
                           notified=notified,
                           booked=booked,
                           total_count=len(entries))


@waitlist_bp.route('/remove/<waitlist_id>', methods=['POST'])
@login_required
def remove_entry(waitlist_id):
    """Remove an entry from waitlist"""
    user_id = str(session.get('user_id'))
    
    service = get_waitlist_service(user_id)
    
    if service.remove_from_waitlist(waitlist_id):
        flash('Bekleme listesinden kaldırıldı.', 'success')
    else:
        flash('Kayıt bulunamadı.', 'error')
    
    return redirect(url_for('waitlist.waitlist_dashboard'))


@waitlist_bp.route('/mark-booked/<waitlist_id>', methods=['POST'])
@login_required
def mark_booked(waitlist_id):
    """Mark waitlist entry as booked"""
    user_id = str(session.get('user_id'))
    
    service = get_waitlist_service(user_id)
    service.mark_as_booked(waitlist_id)
    
    flash('Kayıt randevuya dönüştürüldü olarak işaretlendi.', 'success')
    return redirect(url_for('waitlist.waitlist_dashboard'))


# ==================
# Claim Booking (Special Link)
# ==================

@waitlist_bp.route('/claim/<waitlist_id>/<token>', methods=['GET', 'POST'])
def claim_booking(waitlist_id, token):
    """Handle booking claim from email link"""
    # Get waitlist entry
    entry = get_data(f'waitlist/{waitlist_id}')
    
    if not entry:
        flash('Geçersiz bekleme listesi kaydı.', 'error')
        return render_template('appointments/waitlist_expired.html', reason='not_found')
    
    # Verify token
    if entry.get('booking_token') != token:
        flash('Geçersiz veya kullanılmış link.', 'error')
        return render_template('appointments/waitlist_expired.html', reason='invalid_token')
    
    # Check if already booked
    if entry.get('status') == 'booked':
        flash('Bu randevu zaten alınmış.', 'info')
        return render_template('appointments/waitlist_expired.html', reason='already_booked')
    
    # Check expiry
    expires_at_str = entry.get('booking_expires_at')
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if datetime.now() > expires_at:
                # Link expired - notify next person in line
                _notify_next_in_queue(entry)
                flash('Bu linkin süresi dolmuş. Bir sonraki sıradaki kişiye haber verildi.', 'warning')
                return render_template('appointments/waitlist_expired.html', reason='expired')
        except:
            pass
    
    # Get instructor info
    user_id = entry.get('user_id')
    users = get_data('users') or {}
    instructor = users.get(str(user_id), {})
    company_name = instructor.get('company_name', '').strip()
    full_name = f"{instructor.get('first_name', '')} {instructor.get('last_name', '')}".strip()
    instructor_name = company_name or full_name or 'Eğitmen'
    
    slot_date = entry.get('slot_date') or entry.get('preferred_date')
    slot_time = entry.get('slot_time') or entry.get('preferred_time')
    
    if request.method == 'POST':
        # Create appointment request
        try:
            all_appointments = get_data('appointments') or {}
            new_id = max([int(k) for k in all_appointments.keys() if str(k).isdigit()], default=0) + 1
            
            import secrets
            cancel_token = secrets.token_urlsafe(32)
            
            new_appointment = {
                'id': new_id,
                'user_id': str(user_id),
                'title': f"{entry.get('client_name')} - Bekleme Listesi Randevusu",
                'description': f"Bekleme listesinden alınan randevu. Not: {entry.get('notes', '')}",
                'appointment_date': slot_date,
                'appointment_time': slot_time,
                'duration': entry.get('slot_duration', 60),
                'status': 'pending',
                'client_name': entry.get('client_name'),
                'client_phone': entry.get('client_phone'),
                'client_email': entry.get('client_email'),
                'cancel_token': cancel_token,
                'from_waitlist': True,
                'waitlist_id': waitlist_id,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
            }
            
            set_data(f'appointments/{new_id}', new_appointment)
            
            # Mark waitlist entry as booked
            update_data(f'waitlist/{waitlist_id}', {
                'status': 'booked',
                'booked_at': datetime.now().isoformat(),
                'appointment_id': new_id
            })
            
            flash('Randevu talebiniz oluşturuldu! Eğitmenin onayını bekleyin.', 'success')
            return render_template('appointments/waitlist_booked.html',
                                   appointment=new_appointment,
                                   instructor_name=instructor_name)
            
        except Exception as e:
            logger.error(f"Error creating appointment from waitlist: {e}")
            flash(f'Randevu oluşturulurken hata: {str(e)}', 'error')
    
    # GET - Show confirmation page
    return render_template('appointments/claim_booking.html',
                           entry=entry,
                           instructor_name=instructor_name,
                           slot_date=slot_date,
                           slot_time=slot_time,
                           waitlist_id=waitlist_id,
                           token=token)


def _notify_next_in_queue(expired_entry: dict):
    """Notify next person in waitlist queue when someone's link expires"""
    try:
        user_id = expired_entry.get('user_id')
        slot_date = expired_entry.get('slot_date') or expired_entry.get('preferred_date')
        slot_time = expired_entry.get('slot_time') or expired_entry.get('preferred_time')
        slot_duration = expired_entry.get('slot_duration', 60)
        
        # Mark current entry as expired
        update_data(f"waitlist/{expired_entry.get('id')}", {
            'status': 'expired',
            'expired_at': datetime.now().isoformat()
        })
        
        # Notify next in queue
        service = get_waitlist_service(user_id)
        service.notify_waitlist_on_cancel(slot_date, slot_time, slot_duration)
        
    except Exception as e:
        logger.error(f"Error notifying next in queue: {e}")


# ==================
# Public Waitlist Form
# ==================

@waitlist_bp.route('/public/<unique_link>', methods=['GET', 'POST'])
def public_waitlist_form(unique_link):
    """Public waitlist registration form"""
    # Find instructor by unique link
    users = get_data('users') or {}
    instructor = None
    instructor_id = None
    
    for uid, user in users.items():
        if user.get('unique_link') == unique_link:
            instructor = user
            instructor_id = uid
            break
    
    if not instructor:
        flash('Geçersiz link.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # IP Rate limit check
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        if not waitlist_rate_limiter.is_allowed(client_ip):
            flash('Çok fazla istek gönderdiniz. Lütfen bir süre bekleyin ve tekrar deneyin.', 'error')
        else:
            client_name = request.form.get('client_name', '').strip()
            client_email = request.form.get('client_email', '').strip()
            client_phone = request.form.get('client_phone', '').strip()
            preferred_date = request.form.get('preferred_date', '').strip()
            preferred_time = request.form.get('preferred_time', '').strip()
            notes = request.form.get('notes', '').strip()
            
            # Validation
            if not client_name or not client_email or not preferred_date:
                flash('Lütfen zorunlu alanları doldurun.', 'error')
            else:
                try:
                    service = get_waitlist_service(instructor_id)
                    waitlist_id = service.add_to_waitlist(
                        client_name=client_name,
                        client_email=client_email,
                        client_phone=client_phone,
                        preferred_date=preferred_date,
                        preferred_time=preferred_time,
                        notes=notes
                    )
                    
                    flash('Bekleme listesine başarıyla eklendiniz! Randevu müsait olduğunda bilgilendirileceksiniz.', 'success')
                    return redirect(url_for('waitlist.public_waitlist_success'))
                except ValueError as e:
                    # Rate limit or duplicate error
                    flash(str(e), 'error')
    
    company_name = instructor.get('company_name', '').strip()
    full_name = f"{instructor.get('first_name', '')} {instructor.get('last_name', '')}".strip()
    instructor_name = company_name or full_name or instructor.get('email', 'Eğitmen')
    
    return render_template('appointments/public_waitlist.html',
                           instructor=instructor,
                           instructor_name=instructor_name,
                           unique_link=unique_link)


@waitlist_bp.route('/success')
def public_waitlist_success():
    """Success page after waitlist registration"""
    return render_template('appointments/waitlist_success.html')


# ==================
# API Endpoints
# ==================

@waitlist_bp.route('/api/count')
@login_required
def api_waitlist_count():
    """Get waitlist count for dashboard badge"""
    user_id = str(session.get('user_id'))
    service = get_waitlist_service(user_id)
    
    return jsonify({
        'count': service.get_waitlist_count()
    })


@waitlist_bp.route('/api/entries')
@login_required
def api_waitlist_entries():
    """Get all waitlist entries as JSON"""
    user_id = str(session.get('user_id'))
    service = get_waitlist_service(user_id)
    
    entries = service.get_user_waitlist()
    
    return jsonify({
        'entries': entries,
        'total': len(entries)
    })

