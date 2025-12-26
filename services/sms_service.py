"""
SMS Service for sending appointment reminders
"""
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

class SMSService:
    """SMS service for sending appointment reminders"""
    
    def __init__(self):
        self.api_key = os.getenv('SMS_API_KEY')
        self.api_url = os.getenv('SMS_API_URL', 'https://api.sms-provider.com/send')
        self.sender_name = os.getenv('SMS_SENDER_NAME', 'Randevu Sistemi')
        
    def send_sms(self, phone_number: str, message: str, user_id: int, client_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Send SMS message
        
        Args:
            phone_number: Recipient phone number
            message: SMS message content
            user_id: ID of the user sending the SMS
            client_id: ID of the client (optional)
            
        Returns:
            Dict with status, message_id, and cost
        """
        try:
            # Clean phone number (remove spaces, add country code if needed)
            clean_phone = self._clean_phone_number(phone_number)
            
            # Prepare SMS data
            sms_data = {
                'to': clean_phone,
                'message': message,
                'from': self.sender_name
            }
            
            # Add API key to headers
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json; charset=utf-8'
            }
            
            # Send SMS via API
            response = requests.post(
                self.api_url,
                json=sms_data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'status': 'sent',
                    'message_id': result.get('message_id'),
                    'cost': result.get('cost', 0.0),
                    'provider': 'sms_provider'
                }
            else:
                logger.error(f"SMS API error: {response.status_code} - {response.text}")
                return {
                    'status': 'failed',
                    'error_message': f"API error: {response.status_code}",
                    'cost': 0.0,
                    'provider': 'sms_provider'
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"SMS request failed: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'cost': 0.0,
                'provider': 'sms_provider'
            }
        except Exception as e:
            logger.error(f"SMS service error: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'cost': 0.0,
                'provider': 'sms_provider'
            }
    
    def _clean_phone_number(self, phone: str) -> str:
        """Clean and format phone number"""
        # Remove all non-digit characters
        clean_phone = ''.join(filter(str.isdigit, phone))
        
        # Add country code if not present (assuming Turkey +90)
        if not clean_phone.startswith('90') and len(clean_phone) == 10:
            clean_phone = '90' + clean_phone
        elif clean_phone.startswith('0') and len(clean_phone) == 11:
            clean_phone = '90' + clean_phone[1:]
            
        return clean_phone
    
    def create_reminder_message(self, appointment_title: str, appointment_date: str, 
                               appointment_time: str, company_name: str) -> str:
        """
        Create SMS reminder message
        
        Args:
            appointment_title: Title of the appointment
            appointment_date: Date of the appointment
            appointment_time: Time of the appointment
            company_name: Name of the company
            
        Returns:
            Formatted SMS message
        """
        message = f"""Merhaba,

{company_name} ile {appointment_title} randevunuz yarın {appointment_date} tarihinde {appointment_time} saatinde gerçekleşecektir.

Randevu detayları:
- Tarih: {appointment_date}
- Saat: {appointment_time}
- Konu: {appointment_title}

Randevunuzu iptal etmek veya değiştirmek için lütfen bizimle iletişime geçin.

İyi günler,
{company_name}"""
        
        # Ensure proper UTF-8 encoding
        return message.encode('utf-8').decode('utf-8')
    
    def send_reminder_sms(self, appointment, user, client=None):
        """
        Send reminder SMS for an appointment
        
        Args:
            appointment: Appointment object or dict
            user: User object or dict (appointment owner)
            client: Client object or dict (optional)
            
        Returns:
            Dict with SMS sending result
        """
        # Helper to get attribute or dict item
        def get_val(obj, attr):
            if isinstance(obj, dict):
                return obj.get(attr)
            return getattr(obj, attr, None)

        # Get recipient phone number
        client_phone = get_val(client, 'phone') if client else None
        user_phone = get_val(user, 'phone')
        
        if client_phone:
            phone_number = client_phone
        elif user_phone:
            phone_number = user_phone
        else:
            return {
                'status': 'failed',
                'error_message': 'No phone number available for reminder',
                'cost': 0.0,
                'provider': 'sms_provider'
            }
        
        # Parse dates if they are strings (Firebase case)
        app_date = get_val(appointment, 'appointment_date')
        app_time = get_val(appointment, 'appointment_time')
        
        # If they are datetime objects (SQLAlchemy case), format them
        if hasattr(app_date, 'strftime'):
            app_date = app_date.strftime('%d.%m.%Y')
        if hasattr(app_time, 'strftime'):
            app_time = app_time.strftime('%H:%M')
        # String ise ve saniye içeriyorsa temizle (Firebase'den gelen veri için)
        elif isinstance(app_time, str) and len(app_time) > 5:
            app_time = app_time[:5]
            
        # User company name
        company_name = get_val(user, 'company_display_name') or get_val(user, 'company_name') or "Randevu Sistemi"

        # Create reminder message
        message = self.create_reminder_message(
            appointment_title=get_val(appointment, 'title'),
            appointment_date=app_date,
            appointment_time=app_time,
            company_name=company_name
        )
        
        # Send SMS
        return self.send_sms(
            phone_number=phone_number,
            message=message,
            user_id=get_val(user, 'id'),
            client_id=get_val(client, 'id') if client else None
        )


# Mock SMS service for development/testing
class MockSMSService(SMSService):
    """Mock SMS service for development and testing"""
    
    def send_sms(self, phone_number: str, message: str, user_id: int, client_id: Optional[int] = None) -> Dict[str, Any]:
        """Mock SMS sending - just logs the message"""
        logger.info(f"Mock SMS sent to {phone_number}: {message[:50]}...")
        return {
            'status': 'sent',
            'message_id': f'mock_{datetime.now().timestamp()}',
            'cost': 0.1,
            'provider': 'mock_provider'
        }


def get_sms_service():
    """Get SMS service instance based on environment"""
    if os.getenv('FLASK_ENV') == 'development' or not os.getenv('SMS_API_KEY'):
        return MockSMSService()
    return SMSService()
