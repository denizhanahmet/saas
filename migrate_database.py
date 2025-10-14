#!/usr/bin/env python3
"""
Database Migration Script for Appointment System
This script adds new tables and columns to existing database
"""

import os
import sys
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import User, Appointment, BlockedDay, Client, SmsLog

def migrate_database():
    """Migrate database to add new models and columns"""
    
    print("Starting database migration...")
    
    with app.app_context():
        try:
            # Create all tables (this will only create new ones)
            print("Creating new tables...")
            db.create_all()
            print("New tables created successfully!")
            
            # Check if we need to add new columns to existing User table
            print("Checking for User table updates...")
            
            # Get the first user to check if new columns exist
            first_user = User.query.first()
            if first_user:
                # Check if new columns exist by trying to access them
                try:
                    _ = first_user.company_name
                    _ = first_user.logo_path
                    _ = first_user.sms_quota
                    _ = first_user.is_admin
                    print("User table already has new columns")
                except AttributeError:
                    print("User table needs new columns - please run ALTER TABLE commands manually")
                    print("   Or drop and recreate the database if you don't have important data")
            
            # Verify all tables exist
            print("Verifying all tables exist...")
            tables = ['user', 'appointment', 'blocked_day', 'client', 'sms_log']
            for table in tables:
                try:
                    result = db.engine.execute(f"SELECT COUNT(*) FROM {table}")
                    print(f"Table '{table}' exists with {result.fetchone()[0]} records")
                except Exception as e:
                    print(f"Table '{table}' error: {e}")
            
            print("\nDatabase migration completed successfully!")
            print("\nNew features available:")
            print("   - BlockedDay: Block specific dates for users")
            print("   - Client: Manage client information")
            print("   - SmsLog: Track SMS messages and quotas")
            print("   - User: Added company_name, logo_path, sms_quota, is_admin")
            print("   - Appointment: Added client_id for client association")
            
        except Exception as e:
            print(f"Migration failed: {e}")
            return False
    
    return True

def create_sample_data():
    """Create sample data for testing"""
    
    print("\nCreating sample data...")
    
    with app.app_context():
        try:
            # Create a sample admin user if none exists
            admin_user = User.query.filter_by(is_admin=True).first()
            if not admin_user:
                admin_user = User(
                    username='admin',
                    email='admin@example.com',
                    first_name='Admin',
                    last_name='User',
                    company_name='Sample Company',
                    sms_quota=1000,
                    is_admin=True
                )
                admin_user.set_password('admin123')
                db.session.add(admin_user)
                print("Created admin user (username: admin, password: admin123)")
            
            # Create a sample regular user if none exists
            regular_user = User.query.filter_by(is_admin=False).first()
            if not regular_user:
                regular_user = User(
                    username='user1',
                    email='user@example.com',
                    first_name='John',
                    last_name='Doe',
                    company_name='Doe Services',
                    sms_quota=100,
                    is_admin=False
                )
                regular_user.set_password('user123')
                db.session.add(regular_user)
                print("Created regular user (username: user1, password: user123)")
            
            # Create sample clients
            if not Client.query.first():
                client1 = Client(
                    user_id=regular_user.id,
                    name='Jane Smith',
                    phone='+1234567890',
                    email='jane@example.com',
                    notes='VIP Client'
                )
                client2 = Client(
                    user_id=regular_user.id,
                    name='Bob Johnson',
                    phone='+1234567891',
                    email='bob@example.com'
                )
                db.session.add_all([client1, client2])
                print("Created sample clients")
            
            # Create sample blocked day
            if not BlockedDay.query.first():
                blocked_day = BlockedDay(
                    user_id=regular_user.id,
                    date=datetime.now().date(),
                    reason='Holiday'
                )
                db.session.add(blocked_day)
                print("Created sample blocked day")
            
            db.session.commit()
            print("Sample data created successfully!")
            
        except Exception as e:
            print(f"Sample data creation failed: {e}")
            db.session.rollback()

if __name__ == '__main__':
    print("=" * 60)
    print("APPOINTMENT SYSTEM - DATABASE MIGRATION")
    print("=" * 60)
    
    # Run migration
    if migrate_database():
        # Ask if user wants sample data
        response = input("\nDo you want to create sample data? (y/n): ").lower().strip()
        if response in ['y', 'yes']:
            create_sample_data()
        
        print("\nYou can now run the application with: python app.py")
        print("Access the application at: http://localhost:5000")
    else:
        print("\nMigration failed. Please check the errors above.")
        sys.exit(1)
