"""
Waitlist Service - Queue management for fully booked slots
"""
import logging
import secrets
import threading
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from flask import current_app
from flask_mail import Message

from firebase_realtime import get_data, set_data, update_data, delete_data

logger = logging.getLogger(__name__)


class WaitlistService:
    """Service for managing waitlist entries"""
    
    def __init__(self, user_id: str):
        self.user_id = str(user_id)
    
    def add_to_waitlist(self, client_name: str, client_email: str,
                        client_phone: str, preferred_date: str,
                        preferred_time: str, notes: str = None) -> str:
        """
        Add a client to the waitlist
        Returns: waitlist entry ID or None if blocked by rate limit
        Raises: ValueError if duplicate or rate limit exceeded
        """
        # Normalize email
        client_email = client_email.lower().strip()
        
        # Check for duplicates and rate limits
        self._check_rate_limits(client_email, preferred_date)
        
        waitlist_id = f"wl_{uuid.uuid4().hex[:12]}"
        
        entry = {
            'id': waitlist_id,
            'user_id': self.user_id,
            'client_name': client_name,
            'client_email': client_email,
            'client_phone': client_phone,
            'preferred_date': preferred_date,
            'preferred_time': preferred_time,
            'notes': notes,
            'status': 'waiting',
            'created_at': datetime.now().isoformat(),
            'notified_at': None,
            'expires_at': None
        }
        
        set_data(f'waitlist/{waitlist_id}', entry)
        logger.info(f"Added to waitlist: {waitlist_id} for user {self.user_id}")
        
        return waitlist_id
    
    def _check_rate_limits(self, client_email: str, preferred_date: str):
        """
        Check rate limits for waitlist registration
        Raises ValueError if limits exceeded
        """
        all_waitlist = get_data('waitlist') or {}
        
        same_date_count = 0
        total_active_count = 0
        max_per_date = 1  # Same email can only register once per date
        max_active_total = 3  # Max 3 active waitlist entries per email per instructor
        
        for wl_id, entry in all_waitlist.items():
            if str(entry.get('user_id')) != self.user_id:
                continue
            
            entry_email = (entry.get('client_email') or '').lower().strip()
            if entry_email != client_email:
                continue
            
            entry_status = entry.get('status')
            
            # Skip completed/expired entries
            if entry_status in ['booked', 'expired']:
                continue
            
            # Check same date
            if entry.get('preferred_date') == preferred_date and entry_status in ['waiting', 'notified']:
                same_date_count += 1
            
            # Count active entries
            if entry_status in ['waiting', 'notified']:
                total_active_count += 1
        
        if same_date_count >= max_per_date:
            raise ValueError(f"Bu e-posta adresi zaten {preferred_date} tarihi için bekleme listesinde kayıtlı.")
        
        if total_active_count >= max_active_total:
            raise ValueError(f"Bu e-posta adresi ile en fazla {max_active_total} aktif bekleme kaydı oluşturabilirsiniz.")
    
    def remove_from_waitlist(self, waitlist_id: str) -> bool:
        """Remove an entry from waitlist"""
        waitlist = get_data(f'waitlist/{waitlist_id}')
        
        if not waitlist:
            return False
        
        if str(waitlist.get('user_id')) != self.user_id:
            return False
        
        delete_data(f'waitlist/{waitlist_id}')
        logger.info(f"Removed from waitlist: {waitlist_id}")
        return True
    
    def get_user_waitlist(self, status: str = None) -> List[dict]:
        """Get all waitlist entries for this user"""
        all_waitlist = get_data('waitlist') or {}
        
        entries = []
        for wl_id, entry in all_waitlist.items():
            if str(entry.get('user_id')) != self.user_id:
                continue
            
            if status and entry.get('status') != status:
                continue
            
            entry['id'] = wl_id
            entries.append(entry)
        
        # Sort by created_at (oldest first - FIFO)
        entries.sort(key=lambda x: x.get('created_at', ''))
        return entries
    
    def get_waitlist_for_slot(self, target_date: str, target_time: str) -> List[dict]:
        """Get waitlist entries for a specific slot (matches by date, optionally by time)"""
        all_waitlist = get_data('waitlist') or {}
        
        logger.info(f"Looking for waitlist entries: date={target_date}, time={target_time}, user={self.user_id}")
        
        entries = []
        for wl_id, entry in all_waitlist.items():
            if str(entry.get('user_id')) != self.user_id:
                continue
            if entry.get('status') != 'waiting':
                continue
            if entry.get('preferred_date') != target_date:
                continue
            
            # Time matching: accept if waitlist time is empty OR matches
            waitlist_time = entry.get('preferred_time', '')
            if waitlist_time and target_time and waitlist_time != target_time:
                continue
            
            logger.info(f"Found matching waitlist entry: {wl_id}")
            entry['id'] = wl_id
            entries.append(entry)
        
        entries.sort(key=lambda x: x.get('created_at', ''))
        logger.info(f"Total matching entries: {len(entries)}")
        return entries
    
    def notify_waitlist_on_cancel(self, cancelled_date: str, cancelled_time: str,
                                   slot_duration: int = 60) -> int:
        """
        Notify waitlist entries when a slot becomes available
        Returns: number of notifications sent
        """
        # Find matching waitlist entries
        entries = self.get_waitlist_for_slot(cancelled_date, cancelled_time)
        
        if not entries:
            logger.info(f"No waitlist entries for {cancelled_date} {cancelled_time}")
            return 0
        
        # Notify first person in queue (FIFO)
        first_entry = entries[0]
        
        # Get instructor info
        users = get_data('users') or {}
        instructor = users.get(self.user_id, {})
        
        # Use company name first, then full name, then email as fallback
        company_name = instructor.get('company_name', '').strip()
        full_name = f"{instructor.get('first_name', '')} {instructor.get('last_name', '')}".strip()
        instructor_name = company_name or full_name or instructor.get('email', 'Eğitmen')
        
        # Generate special booking token (expires in 24 hours)
        import secrets
        booking_token = secrets.token_urlsafe(32)
        expiry_hours = 24
        expires_at = (datetime.now() + timedelta(hours=expiry_hours)).isoformat()
        
        # Update waitlist entry with booking token
        update_data(f"waitlist/{first_entry['id']}", {
            'booking_token': booking_token,
            'booking_expires_at': expires_at,
            'slot_date': cancelled_date,
            'slot_time': cancelled_time,
            'slot_duration': slot_duration
        })
        
        # Send email notification with booking link
        email_sent = self._send_availability_email(
            first_entry, instructor_name, 
            cancelled_date, cancelled_time,
            booking_token, expiry_hours
        )
        
        # Send SMS notification (if phone number available)
        sms_sent = self._send_availability_sms(
            first_entry, instructor_name,
            cancelled_date, cancelled_time,
            booking_token
        )
        
        if email_sent or sms_sent:
            # Update waitlist entry status
            update_data(f"waitlist/{first_entry['id']}", {
                'status': 'notified',
                'notified_at': datetime.now().isoformat(),
                'notification_email': email_sent,
                'notification_sms': sms_sent
            })
            logger.info(f"Notified waitlist entry: {first_entry['id']} (email={email_sent}, sms={sms_sent})")
            return 1
        
        return 0
    
    def _send_availability_email(self, entry: dict, instructor_name: str,
                                  available_date: str, available_time: str,
                                  booking_token: str = None, expiry_hours: int = 24) -> bool:
        """Send email notification about slot availability with booking link"""
        try:
            # Format date for display
            try:
                date_obj = datetime.strptime(available_date, '%Y-%m-%d')
                formatted_date = date_obj.strftime('%d.%m.%Y')
            except:
                formatted_date = available_date
            
            client_email = entry.get('client_email')
            client_name = entry.get('client_name', 'Değerli Müşterimiz')
            waitlist_id = entry.get('id')
            
            if not client_email:
                return False
            
            # Build booking link
            from flask import url_for
            booking_url = url_for('waitlist.claim_booking', 
                                  waitlist_id=waitlist_id, 
                                  token=booking_token, 
                                  _external=True) if booking_token else None
            
            subject = f"🎉 İstediğiniz Randevu Saati Müsait! - {instructor_name}"
            
            # Button HTML if booking link available
            button_html = ""
            if booking_url:
                button_html = f"""
                    <div style="text-align: center; margin: 25px 0;">
                        <a href="{booking_url}" style="display: inline-block; background: linear-gradient(135deg, #10b981, #059669); color: white; padding: 14px 32px; font-size: 16px; font-weight: bold; text-decoration: none; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.15);">
                            ✅ Randevuyu Hemen Al
                        </a>
                    </div>
                    <p style="font-size: 13px; color: #dc2626; text-align: center;">
                        ⏰ Bu link {expiry_hours} saat içinde geçerliliğini yitirecektir!
                    </p>
                """
            
            html_body = f"""
            <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f8fafc; padding: 20px;">
                <div style="background: linear-gradient(135deg, #3b82f6, #8b5cf6); padding: 30px; border-radius: 16px 16px 0 0; text-align: center;">
                    <h1 style="color: white; margin: 0; font-size: 24px;">🎉 Harika Haber!</h1>
                </div>
                <div style="background: white; padding: 30px; border-radius: 0 0 16px 16px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <p style="font-size: 16px; color: #374151;">Merhaba <strong>{client_name}</strong>,</p>
                    
                    <p style="font-size: 16px; color: #374151;">
                        Bekleme listesine eklediğiniz randevu saati artık müsait!
                    </p>
                    
                    <div style="background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 12px; padding: 20px; margin: 20px 0;">
                        <p style="margin: 0; font-size: 14px; color: #0369a1;">
                            <strong>📅 Tarih:</strong> {formatted_date}<br>
                            <strong>🕐 Saat:</strong> {available_time}<br>
                            <strong>🏢 Şirket:</strong> {instructor_name}
                        </p>
                    </div>
                    
                    {button_html}
                    
                    <p style="font-size: 14px; color: #6b7280; margin-top: 30px;">
                        Teşekkürler,<br>
                        <strong>{instructor_name}</strong>
                    </p>
                </div>
            </div>
            """
            
            text_body = f"""
Merhaba {client_name},

Bekleme listesine eklediğiniz randevu saati artık müsait!

Tarih: {formatted_date}
Saat: {available_time}
Şirket: {instructor_name}

{"Randevunuzu almak için: " + booking_url if booking_url else "Lütfen randevu almak için iletişime geçin."}

Bu link {expiry_hours} saat geçerlidir.

Teşekkürler,
{instructor_name}
            """
            
            # Send async email
            from flask import current_app
            app = current_app._get_current_object()
            
            msg = Message(
                subject=subject,
                recipients=[client_email],
                body=text_body,
                html=html_body
            )
            
            def send_async(app, msg):
                with app.app_context():
                    try:
                        mail = app.extensions.get('mail')
                        if mail:
                            mail.send(msg)
                            logger.info(f"Waitlist notification sent to {client_email}")
                    except Exception as e:
                        logger.error(f"Failed to send waitlist email: {e}")
            
            thread = threading.Thread(target=send_async, args=(app, msg))
            thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending waitlist notification: {e}")
            return False
    
    def _send_availability_sms(self, entry: dict, instructor_name: str,
                                available_date: str, available_time: str,
                                booking_token: str = None) -> bool:
        """Send SMS notification about slot availability"""
        try:
            client_phone = entry.get('client_phone')
            client_name = entry.get('client_name', '')
            waitlist_id = entry.get('id')
            
            if not client_phone:
                logger.info(f"No phone number for waitlist entry {waitlist_id}, skipping SMS")
                return False
            
            # Format date for display
            try:
                date_obj = datetime.strptime(available_date, '%Y-%m-%d')
                formatted_date = date_obj.strftime('%d.%m.%Y')
            except:
                formatted_date = available_date
            
            # Build short booking URL
            from flask import url_for, current_app
            
            booking_url = ""
            if booking_token:
                booking_url = url_for('waitlist.claim_booking', 
                                      waitlist_id=waitlist_id, 
                                      token=booking_token, 
                                      _external=True)
            
            # Compose short SMS message (Twilio trial has character limit)
            message = f"{instructor_name}: {formatted_date} {available_time} randevunuz musait! "
            if booking_url:
                message += f"Almak icin: {booking_url}"
            else:
                message += "Lutfen iletisime gecin."
            
            # Send SMS via SMS service
            from services.sms_service import get_sms_service
            
            app = current_app._get_current_object()
            
            def send_sms_async(app, phone, msg, user_id):
                with app.app_context():
                    try:
                        sms_service = get_sms_service()
                        result = sms_service.send_sms(phone, msg, user_id)
                        if result.get('status') == 'sent':
                            logger.info(f"Waitlist SMS sent to {phone}")
                        else:
                            logger.warning(f"Waitlist SMS failed: {result.get('error_message')}")
                    except Exception as e:
                        logger.error(f"Failed to send waitlist SMS: {e}")
            
            thread = threading.Thread(
                target=send_sms_async, 
                args=(app, client_phone, message, self.user_id)
            )
            thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending waitlist SMS: {e}")
            return False
    
    def mark_as_booked(self, waitlist_id: str) -> bool:
        """Mark waitlist entry as booked (converted to appointment)"""
        update_data(f"waitlist/{waitlist_id}", {
            'status': 'booked',
            'booked_at': datetime.now().isoformat()
        })
        return True
    
    def expire_old_entries(self, days: int = 7) -> int:
        """Expire waitlist entries older than X days"""
        all_waitlist = get_data('waitlist') or {}
        
        expired_count = 0
        for wl_id, entry in all_waitlist.items():
            if str(entry.get('user_id')) != self.user_id:
                continue
            if entry.get('status') != 'waiting':
                continue
            
            created_str = entry.get('created_at', '')
            try:
                created = datetime.fromisoformat(created_str)
                if (datetime.now() - created).days > days:
                    update_data(f"waitlist/{wl_id}", {'status': 'expired'})
                    expired_count += 1
                    logger.info(f"Expired old waitlist entry: {wl_id}")
            except:
                continue
        
        return expired_count
    
    def check_expired_bookings(self) -> int:
        """Check for expired booking tokens and notify next in queue"""
        all_waitlist = get_data('waitlist') or {}
        
        notified_count = 0
        for wl_id, entry in all_waitlist.items():
            if str(entry.get('user_id')) != self.user_id:
                continue
            if entry.get('status') != 'notified':
                continue
            
            expires_at_str = entry.get('booking_expires_at')
            if not expires_at_str:
                continue
            
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if datetime.now() > expires_at:
                    # Token expired - mark as expired and notify next
                    slot_date = entry.get('slot_date') or entry.get('preferred_date')
                    slot_time = entry.get('slot_time') or entry.get('preferred_time')
                    slot_duration = entry.get('slot_duration', 60)
                    
                    update_data(f"waitlist/{wl_id}", {
                        'status': 'expired',
                        'expired_at': datetime.now().isoformat()
                    })
                    
                    # Notify next in queue
                    self.notify_waitlist_on_cancel(slot_date, slot_time, slot_duration)
                    notified_count += 1
                    logger.info(f"Expired booking token, notified next: {wl_id}")
            except Exception as e:
                logger.error(f"Error checking expired booking: {e}")
                continue
        
        return notified_count
    
    def get_waitlist_count(self) -> int:
        """Get total waiting entries count"""
        entries = self.get_user_waitlist(status='waiting')
        return len(entries)


def get_waitlist_service(user_id: str) -> WaitlistService:
    """Factory function to get waitlist service instance"""
    return WaitlistService(user_id)


def cleanup_all_waitlists():
    """Global cleanup for all waitlists - run via scheduler"""
    all_users = get_data('users') or {}
    
    total_expired = 0
    total_notified = 0
    
    for user_id in all_users.keys():
        try:
            service = WaitlistService(user_id)
            total_expired += service.expire_old_entries(days=7)
            total_notified += service.check_expired_bookings()
        except Exception as e:
            logger.error(f"Error in waitlist cleanup for user {user_id}: {e}")
    
    if total_expired > 0 or total_notified > 0:
        logger.info(f"Waitlist cleanup: {total_expired} expired, {total_notified} notified next")
    
    return total_expired, total_notified

