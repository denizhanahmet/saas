"""
SMS Service for sending appointment reminders
Supports Twilio and Mock providers
"""
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class TwilioSMSService:
    """SMS service using Twilio API"""
    
    def __init__(self):
        from twilio.rest import Client
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = os.getenv('TWILIO_PHONE_NUMBER')
        self.client = Client(self.account_sid, self.auth_token)
        
    def send_sms(self, phone_number: str, message: str, user_id: int, client_id: Optional[int] = None) -> Dict[str, Any]:
        """Send SMS via Twilio"""
        try:
            # Clean and format phone number
            clean_phone = self._clean_phone_number(phone_number)
            
            # Send SMS via Twilio
            twilio_message = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=clean_phone
            )
            
            logger.info(f"Twilio SMS sent to {clean_phone}: {twilio_message.sid}")
            
            return {
                'status': 'sent',
                'message_id': twilio_message.sid,
                'cost': 0.0,  # Twilio charges separately
                'provider': 'twilio'
            }
            
        except Exception as e:
            logger.error(f"Twilio SMS failed: {str(e)}")
            return {
                'status': 'failed',
                'error_message': str(e),
                'cost': 0.0,
                'provider': 'twilio'
            }
    
    def _clean_phone_number(self, phone: str) -> str:
        """Clean and format phone number for Twilio (E.164 format)"""
        # Remove all non-digit characters
        clean_phone = ''.join(filter(str.isdigit, phone))
        
        # Turkey phone number formatting
        if clean_phone.startswith('0') and len(clean_phone) == 11:
            clean_phone = '90' + clean_phone[1:]
        elif not clean_phone.startswith('90') and len(clean_phone) == 10:
            clean_phone = '90' + clean_phone
        
        # Add + prefix for E.164 format
        if not clean_phone.startswith('+'):
            clean_phone = '+' + clean_phone
            
        return clean_phone


class MockSMSService:
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
    """Get SMS service instance based on environment configuration"""
    # Check for Twilio config
    if os.getenv('TWILIO_ACCOUNT_SID') and os.getenv('TWILIO_AUTH_TOKEN'):
        logger.info("Using Twilio SMS service")
        return TwilioSMSService()
    
    # Fall back to Mock
    logger.info("Using Mock SMS service (no SMS provider configured)")
    return MockSMSService()
