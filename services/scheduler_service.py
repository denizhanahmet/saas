"""
Scheduler Service for managing appointment reminders
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from apscheduler.schedulers import SchedulerAlreadyRunningError

logger = logging.getLogger(__name__)

class SchedulerService:
    """Service for managing appointment reminder scheduling"""
    
    def __init__(self, db, app):
        self.db = db
        self.app = app
        self.scheduler = None
        self._setup_scheduler()
        
    def _setup_scheduler(self):
        """Setup APScheduler with SQLAlchemy job store"""
        try:
            # Get Flask app instance path
            db_path = os.path.join(self.app.instance_path, 'appointments.db')
            db_url = f'sqlite:///{db_path}'
            
            # Configure job store
            jobstores = {
                'default': SQLAlchemyJobStore(url=db_url)
            }
            
            # Configure executors
            executors = {
                'default': ThreadPoolExecutor(max_workers=10)
            }
            
            # Configure job defaults
            job_defaults = {
                'coalesce': True,
                'max_instances': 1,
                'misfire_grace_time': 300  # 5 minutes
            }
            
            # Create scheduler
            self.scheduler = BackgroundScheduler(
                jobstores=jobstores,
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
            from services.sms_service import get_sms_service
            from app import User, Appointment, BlockedDay, Client, SmsLog
            
            with self.app.app_context():
                # Get appointment with user and client
                appointment = Appointment.query.get(appointment_id)
                if not appointment:
                    logger.error(f"Appointment {appointment_id} not found")
                    return
                
                # Check if appointment is still scheduled
                if appointment.status != 'scheduled':
                    logger.info(f"Appointment {appointment_id} is no longer scheduled, skipping reminder")
                    return
                
                # Get user and client
                user = User.query.get(appointment.user_id)
                client = Client.query.get(appointment.client_id) if appointment.client_id else None
                
                if not user:
                    logger.error(f"User for appointment {appointment_id} not found")
                    return
                
                # Get SMS service
                sms_service = get_sms_service()
                
                # Send reminder SMS
                result = sms_service.send_reminder_sms(appointment, user, client)
                
                # Log SMS in database
                sms_log = SmsLog(
                    user_id=user.id,
                    client_id=client.id if client else None,
                    message=f"Reminder: {appointment.title} - {appointment.appointment_date} {appointment.appointment_time}",
                    status=result['status'],
                    error_message=result.get('error_message'),
                    sms_provider=result.get('provider', 'unknown'),
                    cost=result.get('cost', 0.0)
                )
                
                self.db.session.add(sms_log)
                self.db.session.commit()
                
                logger.info(f"Reminder SMS sent for appointment {appointment_id}: {result['status']}")
            
        except Exception as e:
            logger.error(f"Failed to send reminder SMS for appointment {appointment_id}: {str(e)}")
            # Try to log the error in database
            try:
                from app import User, Appointment, BlockedDay, Client, SmsLog
                
                with self.app.app_context():
                    appointment = Appointment.query.get(appointment_id)
                    if appointment:
                        sms_log = SmsLog(
                            user_id=appointment.user_id,
                            message=f"Reminder failed: {appointment.title}",
                            status='failed',
                            error_message=str(e),
                            sms_provider='scheduler',
                            cost=0.0
                        )
                        self.db.session.add(sms_log)
                        self.db.session.commit()
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
            from app import User, Appointment, BlockedDay, Client, SmsLog
            
            with self.app.app_context():
                # Get all scheduled appointments that are in the future
                now = datetime.now()
                future_appointments = Appointment.query.filter(
                    Appointment.status == 'scheduled',
                    Appointment.appointment_date >= now.date()
                ).all()
            
                scheduled_count = 0
                for appointment in future_appointments:
                    appointment_datetime = appointment.get_datetime()
                    
                    # Calculate reminder time (24 hours before)
                    reminder_time = appointment_datetime - timedelta(hours=24)
                    
                    # Only schedule if reminder time is in the future
                    if reminder_time > now:
                        self.schedule_appointment_reminder(appointment.id, reminder_time)
                        scheduled_count += 1
                
                logger.info(f"Scheduled {scheduled_count} appointment reminders")
                
        except Exception as e:
            logger.error(f"Failed to schedule pending reminders: {str(e)}")
            raise
