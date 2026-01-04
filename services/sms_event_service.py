"""
SMS Event Service - Event-driven SMS notification system
Handles SMS Location Order logic for configurable event triggers
"""
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from firebase_realtime import get_data, set_data

logger = logging.getLogger(__name__)


class SMSEventService:
    """
    Event-driven SMS service that handles Location (event type) and Order (priority/sequence)
    """
    
    # Predefined SMS event locations
    LOCATIONS = {
        'appointment_created': 'Randevu oluşturuldu',
        'appointment_approved': 'Randevu onaylandı',
        'appointment_cancelled': 'Randevu iptal edildi',
        'appointment_rejected': 'Randevu reddedildi',
        'reminder_24h': '24 saat kala hatırlatma',
        'reminder_1h': '1 saat kala hatırlatma',
        'reminder_custom': 'Özel hatırlatma',
    }
    
    # Default SMS templates - Keep under 160 chars for Trial accounts
    DEFAULT_TEMPLATES = {
        'appointment_approved': '{client_name}, {date} {time} randevunuz onaylandi.',
        'appointment_rejected': '{client_name}, randevu talebiniz onaylanmadi.',
        'appointment_cancelled': '{client_name}, {date} randevunuz iptal edildi.',
        'reminder_24h': '{client_name}, yarin saat {time} randevunuz var.',
        'reminder_1h': '{client_name}, 1 saat sonra randevunuz var.',
    }
    
    def __init__(self, sms_service=None):
        """Initialize with optional SMS service dependency injection"""
        self.sms_service = sms_service
        self._events_cache = None
        self._cache_time = None
    
    def get_sms_service(self):
        """Lazy load SMS service"""
        if self.sms_service is None:
            from services.sms_service import get_sms_service
            self.sms_service = get_sms_service()
        return self.sms_service
    
    def get_events(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get all SMS events from Firebase with caching"""
        # Cache for 5 minutes
        if not force_refresh and self._events_cache and self._cache_time:
            if (datetime.utcnow() - self._cache_time).total_seconds() < 300:
                return self._events_cache
        
        self._events_cache = get_data('sms_events') or {}
        self._cache_time = datetime.utcnow()
        return self._events_cache
    
    def get_events_for_location(self, location: str) -> List[Dict[str, Any]]:
        """Get all enabled events for a specific location, sorted by order"""
        events = self.get_events()
        location_events = []
        
        for event_id, event in events.items():
            if event.get('location') == location and event.get('enabled', True):
                event['id'] = event_id
                location_events.append(event)
        
        # Sort by order (lower = higher priority)
        return sorted(location_events, key=lambda e: e.get('order', 100))
    
    def render_template(self, template: str, context: Dict[str, Any]) -> str:
        """
        Render SMS template with context variables
        
        Supported variables:
        - {client_name} - Customer name
        - {client_phone} - Customer phone
        - {company_name} - Company/instructor name
        - {date} - Appointment date
        - {time} - Appointment time
        - {title} - Appointment title
        - {cancel_url} - Cancellation URL
        """
        if not template:
            return ""
        
        # Replace all {variable} patterns
        def replace_var(match):
            var_name = match.group(1)
            return str(context.get(var_name, ''))
        
        rendered = re.sub(r'\{(\w+)\}', replace_var, template)
        return rendered
    
    def check_conditions(self, event: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Check if event conditions are met
        
        Conditions:
        - has_phone: Recipient must have phone number
        - status_in: Appointment status must be in list
        - status_not_in: Appointment status must not be in list
        """
        conditions = event.get('conditions', {})
        
        # Check has_phone condition
        if conditions.get('has_phone', False):
            if not context.get('client_phone'):
                logger.debug(f"Event {event.get('id')}: No phone number, skipping")
                return False
        
        # Check status_in condition
        status_in = conditions.get('status_in')
        if status_in and isinstance(status_in, list):
            if context.get('status') not in status_in:
                logger.debug(f"Event {event.get('id')}: Status not in allowed list")
                return False
        
        # Check status_not_in condition
        status_not_in = conditions.get('status_not_in')
        if status_not_in and isinstance(status_not_in, list):
            if context.get('status') in status_not_in:
                logger.debug(f"Event {event.get('id')}: Status in excluded list")
                return False
        
        return True
    
    def trigger_event(self, location: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Trigger SMS event for a specific location
        
        Args:
            location: Event location (e.g., 'appointment_approved')
            context: Event context with variables:
                - client_name, client_phone, client_email
                - company_name
                - date, time, title
                - status
                - cancel_url (optional)
                - user_id (required for SMS quota tracking)
        
        Returns:
            List of SMS send results
        """
        results = []
        events = self.get_events_for_location(location)
        
        if not events:
            # Use default template if no custom events configured
            default_template = self.DEFAULT_TEMPLATES.get(location)
            if default_template and context.get('client_phone'):
                events = [{
                    'id': f'default_{location}',
                    'location': location,
                    'template': default_template,
                    'enabled': True,
                    'order': 1,
                    'priority': 1,
                    'conditions': {'has_phone': True}
                }]
        
        for event in events:
            try:
                # Check conditions
                if not self.check_conditions(event, context):
                    continue
                
                # Render template
                template = event.get('template', '')
                message = self.render_template(template, context)
                
                if not message:
                    logger.warning(f"Event {event.get('id')}: Empty message after rendering")
                    continue
                
                # Get phone number
                phone = context.get('client_phone')
                if not phone:
                    logger.warning(f"Event {event.get('id')}: No phone number in context")
                    continue
                
                # Send SMS
                sms_service = self.get_sms_service()
                result = sms_service.send_sms(
                    phone_number=phone,
                    message=message,
                    user_id=context.get('user_id'),
                    client_id=context.get('client_id')
                )
                
                result['event_id'] = event.get('id')
                result['location'] = location
                results.append(result)
                
                logger.info(f"SMS event triggered: {location} -> {event.get('id')} -> {result.get('status')}")
                
            except Exception as e:
                logger.error(f"Error triggering SMS event {event.get('id')}: {str(e)}")
                results.append({
                    'event_id': event.get('id'),
                    'location': location,
                    'status': 'failed',
                    'error': str(e)
                })
        
        return results
    
    def create_context_from_appointment(self, appointment: Dict, instructor: Dict, cancel_url: str = None) -> Dict[str, Any]:
        """
        Create event context from appointment and instructor data
        """
        return {
            'client_name': appointment.get('client_name', 'Müşteri'),
            'client_phone': appointment.get('client_phone'),
            'client_email': appointment.get('client_email'),
            'company_name': instructor.get('company_name') or f"{instructor.get('first_name', '')} {instructor.get('last_name', '')}".strip() or "Randevu Sistemi",
            'date': appointment.get('appointment_date'),
            'time': appointment.get('appointment_time'),
            'title': appointment.get('title', 'Randevu'),
            'status': appointment.get('status'),
            'user_id': appointment.get('user_id') or instructor.get('id'),
            'appointment_id': appointment.get('id'),
            'cancel_url': cancel_url or '',
        }


# Default events to seed into Firebase
DEFAULT_EVENTS = {
    'evt_approved': {
        'location': 'appointment_approved',
        'template': 'Sayın {client_name}, {date} saat {time} randevunuz onaylanmıştır. İptal için: {cancel_url}',
        'enabled': True,
        'priority': 1,
        'order': 10,
        'conditions': {'has_phone': True}
    },
    'evt_rejected': {
        'location': 'appointment_rejected',
        'template': 'Sayın {client_name}, randevu talebiniz maalesef onaylanamamıştır.',
        'enabled': True,
        'priority': 1,
        'order': 10,
        'conditions': {'has_phone': True}
    },
    'evt_cancelled': {
        'location': 'appointment_cancelled',
        'template': 'Sayın {client_name}, {date} tarihli randevunuz iptal edilmiştir.',
        'enabled': True,
        'priority': 1,
        'order': 10,
        'conditions': {'has_phone': True}
    },
    'evt_reminder_24h': {
        'location': 'reminder_24h',
        'template': 'Sayın {client_name}, yarın saat {time} randevunuz bulunmaktadır. - {company_name}',
        'enabled': True,
        'priority': 2,
        'order': 10,
        'conditions': {'has_phone': True, 'status_in': ['scheduled', 'approved']}
    },
}


def seed_default_events():
    """Seed default SMS events to Firebase if not exists"""
    existing = get_data('sms_events') or {}
    
    for event_id, event_data in DEFAULT_EVENTS.items():
        if event_id not in existing:
            set_data(f'sms_events/{event_id}', event_data)
            logger.info(f"Seeded SMS event: {event_id}")


# Singleton instance
_event_service_instance = None

def get_event_service() -> SMSEventService:
    """Get singleton SMS event service instance"""
    global _event_service_instance
    if _event_service_instance is None:
        _event_service_instance = SMSEventService()
    return _event_service_instance
