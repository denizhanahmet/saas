#!/usr/bin/env python3
"""
Management script for the scheduler service
"""
import os
import sys
from datetime import datetime, timedelta

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, get_scheduler_service
from model_definitions import create_models

def list_scheduled_jobs():
    """List all scheduled jobs"""
    with app.app_context():
        scheduler = get_scheduler_service()
        if not scheduler:
            print("Scheduler service not available")
            return
        
        jobs = scheduler.get_scheduled_jobs()
        if not jobs:
            print("No scheduled jobs found")
            return
        
        print(f"Found {len(jobs)} scheduled jobs:")
        for job in jobs:
            print(f"  - {job.id}: {job.name} (Next run: {job.next_run_time})")

def schedule_test_reminder():
    """Schedule a test reminder (for testing purposes)"""
    with app.app_context():
        # Get a sample appointment
        User, Appointment, BlockedDay, Client, SmsLog = create_models(db)
        
        appointment = Appointment.query.filter_by(status='scheduled').first()
        if not appointment:
            print("No scheduled appointments found")
            return
        
        scheduler = get_scheduler_service()
        if not scheduler:
            print("Scheduler service not available")
            return
        
        # Schedule reminder for 1 minute from now (for testing)
        test_time = datetime.now() + timedelta(minutes=1)
        scheduler.schedule_appointment_reminder(appointment.id, test_time)
        print(f"Scheduled test reminder for appointment {appointment.id} at {test_time}")

def remove_all_reminders():
    """Remove all scheduled reminders"""
    with app.app_context():
        User, Appointment, BlockedDay, Client, SmsLog = create_models(db)
        
        appointments = Appointment.query.filter_by(status='scheduled').all()
        scheduler = get_scheduler_service()
        
        if not scheduler:
            print("Scheduler service not available")
            return
        
        removed_count = 0
        for appointment in appointments:
            try:
                scheduler.remove_appointment_reminder(appointment.id)
                removed_count += 1
            except Exception as e:
                print(f"Failed to remove reminder for appointment {appointment.id}: {e}")
        
        print(f"Removed {removed_count} scheduled reminders")

def reschedule_all_reminders():
    """Reschedule all pending reminders"""
    with app.app_context():
        scheduler = get_scheduler_service()
        if not scheduler:
            print("Scheduler service not available")
            return
        
        try:
            scheduler.schedule_all_pending_reminders()
            print("All pending reminders have been rescheduled")
        except Exception as e:
            print(f"Failed to reschedule reminders: {e}")

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python manage_scheduler.py <command>")
        print("Commands:")
        print("  list - List all scheduled jobs")
        print("  test - Schedule a test reminder")
        print("  remove - Remove all scheduled reminders")
        print("  reschedule - Reschedule all pending reminders")
        return
    
    command = sys.argv[1]
    
    if command == 'list':
        list_scheduled_jobs()
    elif command == 'test':
        schedule_test_reminder()
    elif command == 'remove':
        remove_all_reminders()
    elif command == 'reschedule':
        reschedule_all_reminders()
    else:
        print(f"Unknown command: {command}")

if __name__ == '__main__':
    main()
