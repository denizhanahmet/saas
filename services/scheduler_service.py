"""
Scheduler Service for managing appointment reminders
"""
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from flask_mail import Message
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.executors.pool import ThreadPoolExecutor

from apscheduler.schedulers import SchedulerAlreadyRunningError
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

class SchedulerService:
    """Service for managing appointment reminder scheduling"""
    
    def __init__(self, app):
        # db parametresi kaldırıldı çünkü Firebase modülleri doğrudan import ediliyor
        self.app = app
        self.scheduler = None
        self.sms_service = None
        self._setup_scheduler()
        
    def _setup_scheduler(self):
        """Setup APScheduler with SQLAlchemy job store"""
        try:
            # Get Flask app instance path

            # SQLAlchemyJobStore ve SQLite kaldırıldı. Sadece memory job store ile başlatılıyor.
            executors = {
                'default': ThreadPoolExecutor(max_workers=10)
            }
            job_defaults = {
                'coalesce': True,
                'max_instances': 1,
                'misfire_grace_time': 300  # 5 minutes
            }
            self.scheduler = BackgroundScheduler(
                executors=executors,
                job_defaults=job_defaults,
                timezone='Europe/Istanbul'
            )
            
            # Add event listeners
            self.scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
            self.scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)
            
            logger.info("Scheduler service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup scheduler: {str(e)}")
            raise
    
    def start(self):
        """Start the scheduler"""
        try:
            if not self.scheduler.running:
                self.scheduler.start()
                logger.info("Scheduler started successfully")
            else:
                logger.warning("Scheduler is already running")
        except SchedulerAlreadyRunningError:
            logger.warning("Scheduler is already running")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {str(e)}")
            raise
    
    def stop(self):
        """Stop the scheduler"""
        try:
            if self.scheduler and self.scheduler.running:
                self.scheduler.shutdown(wait=True)
                logger.info("Scheduler stopped successfully")
        except Exception as e:
            logger.error(f"Failed to stop scheduler: {str(e)}")
    
    def schedule_appointment_reminder(self, appointment_id: int, reminder_time: datetime):
        """
        Schedule a reminder SMS for an appointment
        
        Args:
            appointment_id: ID of the appointment
            reminder_time: When to send the reminder
        """
        try:
            job_id = f"reminder_{appointment_id}"
            
            # Remove existing job if it exists
            self.remove_appointment_reminder(appointment_id)
            
            # Schedule new job
            self.scheduler.add_job(
                func=self._send_reminder_sms,
                trigger='date',
                run_date=reminder_time,
                args=[appointment_id],
                id=job_id,
                name=f"Reminder for appointment {appointment_id}",
                replace_existing=True
            )
            
            logger.info(f"Scheduled reminder for appointment {appointment_id} at {reminder_time}")
            
        except Exception as e:
            logger.error(f"Failed to schedule reminder for appointment {appointment_id}: {str(e)}")
            raise
    
    def remove_appointment_reminder(self, appointment_id: int):
        """
        Remove scheduled reminder for an appointment
        
        Args:
            appointment_id: ID of the appointment
        """
        try:
            job_id = f"reminder_{appointment_id}"
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
                logger.info(f"Removed reminder for appointment {appointment_id}")
        except Exception as e:
            logger.error(f"Failed to remove reminder for appointment {appointment_id}: {str(e)}")
    
    def reschedule_appointment_reminder(self, appointment_id: int, new_reminder_time: datetime):
        """
        Reschedule reminder for an appointment
        
        Args:
            appointment_id: ID of the appointment
            new_reminder_time: New reminder time
        """
        try:
            # Remove existing job
            self.remove_appointment_reminder(appointment_id)
            
            # Schedule new job
            self.schedule_appointment_reminder(appointment_id, new_reminder_time)
            
            logger.info(f"Rescheduled reminder for appointment {appointment_id} to {new_reminder_time}")
            
        except Exception as e:
            logger.error(f"Failed to reschedule reminder for appointment {appointment_id}: {str(e)}")
            raise
    
    def _send_reminder_sms(self, appointment_id: int):
        """
        Send reminder SMS for an appointment
        
        Args:
            appointment_id: ID of the appointment
        """
        try:
            # SQL Modelleri yerine Firebase fonksiyonlarını kullanıyoruz
            from firebase_realtime import get_data, add_data
            from services.sms_service import get_sms_service
            
            with self.app.app_context():
                # 1. Randevuyu Firebase'den çek
                appointment = get_data(f'appointments/{appointment_id}')
                if not appointment:
                    logger.error(f"Appointment {appointment_id} not found")
                    return
                
                # 2. Durum kontrolü (Dictionary erişimi)
                if appointment.get('status') != 'scheduled':
                    logger.info(f"Appointment {appointment_id} is no longer scheduled, skipping reminder")
                    return
                
                # 3. User ve Client verilerini çek
                user_id = appointment.get('user_id')
                client_id = appointment.get('client_id')
                
                user = get_data(f'users/{user_id}') if user_id else None
                client = get_data(f'clients/{client_id}') if client_id else None
                
                if not user:
                    logger.error(f"User for appointment {appointment_id} not found")
                    return
                
                # SMS servisini başlat (Singleton mantığıyla)
                if not self.sms_service:
                    self.sms_service = get_sms_service()
                
                # 4. SMS Gönder (Verileri dict olarak gönderiyoruz, SMS servisi buna uygun olmalı)
                # Not: SMS servisi nesne bekliyorsa, burada basit bir wrapper sınıfı veya
                # SMS servisini dict kabul edecek şekilde güncellemek gerekebilir.
                # Şimdilik SMS servisine dict gönderdiğimizi varsayıyoruz.
                result = self.sms_service.send_reminder_sms(appointment, user, client)
                
                # 5. Logu Firebase'e kaydet
                sms_log = {
                    'user_id': user_id,
                    'client_id': client_id,
                    'message': f"Reminder: {appointment.get('title')} - {appointment.get('appointment_date')} {appointment.get('appointment_time')}",
                    'status': result['status'],
                    'error_message': result.get('error_message'),
                    'sms_provider': result.get('provider', 'unknown'),
                    'cost': result.get('cost', 0.0),
                    'created_at': datetime.now().isoformat()
                }
                
                add_data('sms_logs', sms_log)
                
                logger.info(f"Reminder SMS sent for appointment {appointment_id}: {result['status']}")
                
                # 6. Hatırlatma E-postası Gönder
                client_email = None
                if client:
                    client_email = client.get('email')
                if not client_email:
                    client_email = appointment.get('client_email')
                
                if client_email:
                    try:
                        company_name = user.get('company_display_name') or user.get('company_name') or f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or "Randevu Sistemi"
                        
                        subject = f"Randevu Hatırlatması - {company_name}"
                        
                        # Saat formatı temizliği
                        appt_time_str = str(appointment.get('appointment_time'))
                        if len(appt_time_str) > 5:
                            appt_time_str = appt_time_str[:5]
                        
                        client_name = appointment.get('client_name')
                        if not client_name and client:
                            client_name = client.get('name')
                        
                        body = f"""Sayın {client_name or 'Müşteri'},

{company_name} ile olan randevunuzu hatırlatmak isteriz.

Randevu Detayları:
Tarih: {appointment.get('appointment_date')}
Saat: {appt_time_str}
Konu: {appointment.get('title')}

Saygılarımızla,
{company_name}"""
                        msg = Message(subject, recipients=[client_email], body=body)
                        self.app.extensions['mail'].send(msg)
                        logger.info(f"Reminder email sent to {client_email}")
                    except Exception as e:
                        logger.error(f"Failed to send reminder email: {str(e)}")
            
        except Exception as e:
            logger.error(f"Failed to send reminder SMS for appointment {appointment_id}: {str(e)}")
            # Hata logunu Firebase'e kaydet
            try:
                from firebase_realtime import get_data, add_data
                
                with self.app.app_context():
                    appointment = get_data(f'appointments/{appointment_id}')
                    if appointment:
                        sms_log = {
                            'user_id': appointment.get('user_id'),
                            'message': f"Reminder failed: {appointment.get('title')}",
                            'status': 'failed',
                            'error_message': str(e),
                            'sms_provider': 'scheduler',
                            'cost': 0.0,
                            'created_at': datetime.now().isoformat()
                        }
                        add_data('sms_logs', sms_log)
            except:
                pass
    
    def _job_executed(self, event):
        """Handle job execution events"""
        logger.info(f"Job {event.job_id} executed successfully")
    
    def _job_error(self, event):
        """Handle job error events"""
        logger.error(f"Job {event.job_id} failed: {event.exception}")
    
    def get_scheduled_jobs(self):
        """Get all scheduled jobs"""
        try:
            return self.scheduler.get_jobs()
        except Exception as e:
            logger.error(f"Failed to get scheduled jobs: {str(e)}")
            return []
    
    def get_appointment_reminder_job(self, appointment_id: int):
        """Get reminder job for specific appointment"""
        try:
            job_id = f"reminder_{appointment_id}"
            return self.scheduler.get_job(job_id)
        except Exception as e:
            logger.error(f"Failed to get reminder job for appointment {appointment_id}: {str(e)}")
            return None
    
    def schedule_all_pending_reminders(self):
        """
        Schedule reminders for all pending appointments
        This should be called on application startup
        """
        try:
            from firebase_realtime import get_data
            
            with self.app.app_context():
                # Tüm randevuları çek (Firebase'de filtreleme kısıtlı olduğu için hepsini çekip Python'da filtreliyoruz)
                # Not: Veri büyüdüğünde burası optimize edilmeli (Query parametreleri ile)
                appointments_dict = get_data('appointments') or {}
                now = datetime.now()
            
                scheduled_count = 0
                for app_id, appointment in appointments_dict.items():
                    if appointment.get('status') != 'scheduled':
                        continue

                    # Tarih string'ini datetime'a çevir
                    date_str = appointment.get('appointment_date') # YYYY-MM-DD varsayılıyor
                    time_str = appointment.get('appointment_time') # HH:MM varsayılıyor
                    
                    # Saat verisi saniye/mikrosaniye içeriyorsa temizle (HH:MM al)
                    if time_str and len(str(time_str)) > 5:
                        time_str = str(time_str)[:5]

                    app_dt_str = f"{date_str} {time_str}"
                    appointment_datetime = datetime.strptime(app_dt_str, "%Y-%m-%d %H:%M")
                    
                    # Calculate reminder time (24 hours before)
                    reminder_time = appointment_datetime - timedelta(hours=24)
                    
                    # Only schedule if reminder time is in the future
                    if reminder_time > now:
                        self.schedule_appointment_reminder(app_id, reminder_time)
                        scheduled_count += 1
                
                logger.info(f"Scheduled {scheduled_count} appointment reminders")
                
                # Schedule waitlist cleanup job (hourly)
                self._schedule_waitlist_cleanup()
                
        except Exception as e:
            logger.error(f"Failed to schedule pending reminders: {str(e)}")
            raise
    
    def _schedule_waitlist_cleanup(self):
        """Schedule hourly waitlist cleanup job"""
        try:
            job_id = "waitlist_cleanup"
            
            # Remove existing job if it exists
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            
            # Schedule cleanup to run every hour
            self.scheduler.add_job(
                func=self._run_waitlist_cleanup,
                trigger='interval',
                hours=1,
                id=job_id,
                name="Waitlist Cleanup",
                replace_existing=True
            )
            
            logger.info("Scheduled waitlist cleanup job (hourly)")
            
        except Exception as e:
            logger.error(f"Failed to schedule waitlist cleanup: {str(e)}")
    
    def _run_waitlist_cleanup(self):
        """Run waitlist cleanup"""
        try:
            with self.app.app_context():
                from services.waitlist_service import cleanup_all_waitlists
                cleanup_all_waitlists()
        except Exception as e:
            logger.error(f"Waitlist cleanup failed: {str(e)}")

