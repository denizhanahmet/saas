"""
Scheduling Service - Smart slot suggestions, buffer time, and advance notice
"""
import logging
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Tuple

from firebase_realtime import get_data

logger = logging.getLogger(__name__)


class SchedulingService:
    """Service for smart scheduling features"""
    
    # Default settings
    DEFAULT_BUFFER_TIME = 15  # minutes between appointments
    DEFAULT_MIN_ADVANCE_NOTICE = 2  # hours before appointment
    DEFAULT_SLOT_DURATION = 60  # minutes
    DEFAULT_WORKING_START = "09:00"
    DEFAULT_WORKING_END = "18:00"
    
    def __init__(self, user_id: str):
        self.user_id = str(user_id)
        self._user_data = None
        self._settings = None
    
    @property
    def user_data(self) -> dict:
        """Lazy load user data"""
        if self._user_data is None:
            users = get_data('users') or {}
            self._user_data = users.get(self.user_id, {})
        return self._user_data
    
    @property
    def settings(self) -> dict:
        """Get scheduling settings with defaults"""
        if self._settings is None:
            user_settings = self.user_data.get('scheduling_settings', {})
            self._settings = {
                'buffer_time': user_settings.get('buffer_time', self.DEFAULT_BUFFER_TIME),
                'min_advance_notice': user_settings.get('min_advance_notice', self.DEFAULT_MIN_ADVANCE_NOTICE),
                'slot_duration': user_settings.get('slot_duration', self.DEFAULT_SLOT_DURATION),
            }
        return self._settings
    
    def get_working_hours(self, target_date: date) -> Tuple[time, time]:
        """Get working hours for a specific date"""
        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        day_name = day_names[target_date.weekday()]
        
        working_hours = self.user_data.get('working_hours', {})
        day_hours = working_hours.get(day_name, {})
        
        if not day_hours.get('enabled', True):
            return None, None
        
        start_str = day_hours.get('start', self.DEFAULT_WORKING_START)
        end_str = day_hours.get('end', self.DEFAULT_WORKING_END)
        
        try:
            start_time = datetime.strptime(start_str, '%H:%M').time()
            end_time = datetime.strptime(end_str, '%H:%M').time()
            return start_time, end_time
        except ValueError:
            return time(9, 0), time(18, 0)
    
    def get_user_appointments(self, target_date: date) -> List[dict]:
        """Get user's appointments for a specific date"""
        all_appointments = get_data('appointments') or {}
        
        appointments = []
        date_str = target_date.strftime('%Y-%m-%d')
        
        for apt_id, apt in all_appointments.items():
            if str(apt.get('user_id')) != self.user_id:
                continue
            if apt.get('status') in ['cancelled', 'rejected']:
                continue
            if apt.get('appointment_date') != date_str:
                continue
            
            apt['id'] = apt_id
            appointments.append(apt)
        
        # Sort by time
        def get_time_minutes(apt):
            time_str = apt.get('appointment_time', '00:00')
            try:
                t = datetime.strptime(time_str, '%H:%M').time()
                return t.hour * 60 + t.minute
            except:
                return 0
        
        appointments.sort(key=get_time_minutes)
        return appointments
    
    def check_advance_notice(self, target_datetime: datetime) -> Tuple[bool, str]:
        """Check if appointment meets minimum advance notice requirement"""
        min_hours = self.settings['min_advance_notice']
        now = datetime.now()
        
        min_allowed = now + timedelta(hours=min_hours)
        
        if target_datetime < min_allowed:
            return False, f"Randevular en az {min_hours} saat önceden alınmalıdır."
        
        return True, None
    
    def get_available_slots(self, target_date: date, duration: int = None) -> List[dict]:
        """
        Find all available slots for a given date
        Returns list of {'time': 'HH:MM', 'available': True/False, 'reason': str}
        """
        if duration is None:
            duration = self.settings['slot_duration']
        
        buffer_time = self.settings['buffer_time']
        
        # Get working hours
        work_start, work_end = self.get_working_hours(target_date)
        if work_start is None:
            return []  # Day is closed
        
        # Get existing appointments
        appointments = self.get_user_appointments(target_date)
        
        # Generate slots every 30 minutes
        slots = []
        current_time = datetime.combine(target_date, work_start)
        end_time = datetime.combine(target_date, work_end)
        
        while current_time + timedelta(minutes=duration) <= end_time:
            slot_time = current_time.time()
            slot_str = slot_time.strftime('%H:%M')
            
            is_available, reason = self._check_slot_availability(
                target_date, slot_time, duration, buffer_time, appointments
            )
            
            slots.append({
                'time': slot_str,
                'available': is_available,
                'reason': reason
            })
            
            # Move to next slot (30 min intervals)
            current_time += timedelta(minutes=30)
        
        return slots
    
    def _check_slot_availability(self, target_date: date, slot_time: time, 
                                  duration: int, buffer_time: int,
                                  appointments: List[dict]) -> Tuple[bool, str]:
        """Check if a specific slot is available"""
        now = datetime.now()
        slot_datetime = datetime.combine(target_date, slot_time)
        
        # Check advance notice
        min_hours = self.settings['min_advance_notice']
        if slot_datetime < now + timedelta(hours=min_hours):
            return False, "Minimum bildirim süresi"
        
        slot_start_min = slot_time.hour * 60 + slot_time.minute
        slot_end_min = slot_start_min + duration
        
        for apt in appointments:
            apt_time_str = apt.get('appointment_time', '00:00')
            apt_duration = apt.get('duration', 60)
            
            try:
                apt_time = datetime.strptime(apt_time_str, '%H:%M').time()
            except:
                continue
            
            apt_start_min = apt_time.hour * 60 + apt_time.minute
            apt_end_min = apt_start_min + apt_duration
            
            # Add buffer time
            apt_start_with_buffer = apt_start_min - buffer_time
            apt_end_with_buffer = apt_end_min + buffer_time
            
            # Check overlap (considering buffer)
            if not (slot_end_min <= apt_start_with_buffer or slot_start_min >= apt_end_with_buffer):
                return False, "Dolu"
        
        return True, None
    
    def suggest_slots(self, preferred_date: date, duration: int = None, 
                      limit: int = 5) -> List[dict]:
        """
        Suggest best available slots starting from preferred date
        Returns list of {'date': 'YYYY-MM-DD', 'time': 'HH:MM', 'day_name': str}
        """
        if duration is None:
            duration = self.settings['slot_duration']
        
        suggestions = []
        current_date = preferred_date
        days_checked = 0
        max_days = 14  # Look up to 2 weeks ahead
        
        day_names_tr = {
            0: 'Pazartesi', 1: 'Salı', 2: 'Çarşamba', 
            3: 'Perşembe', 4: 'Cuma', 5: 'Cumartesi', 6: 'Pazar'
        }
        
        while len(suggestions) < limit and days_checked < max_days:
            slots = self.get_available_slots(current_date, duration)
            
            for slot in slots:
                if slot['available'] and len(suggestions) < limit:
                    suggestions.append({
                        'date': current_date.strftime('%Y-%m-%d'),
                        'time': slot['time'],
                        'day_name': day_names_tr[current_date.weekday()],
                        'formatted': f"{day_names_tr[current_date.weekday()]} {current_date.strftime('%d.%m')} - {slot['time']}"
                    })
            
            current_date += timedelta(days=1)
            days_checked += 1
        
        return suggestions
    
    def get_slots_for_date_api(self, date_str: str) -> dict:
        """API response format for slot availability"""
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return {'error': 'Geçersiz tarih formatı', 'slots': []}
        
        slots = self.get_available_slots(target_date)
        available_count = sum(1 for s in slots if s['available'])
        
        return {
            'date': date_str,
            'slots': slots,
            'total': len(slots),
            'available': available_count,
            'settings': {
                'buffer_time': self.settings['buffer_time'],
                'min_advance_notice': self.settings['min_advance_notice'],
                'slot_duration': self.settings['slot_duration']
            }
        }


def get_scheduling_service(user_id: str) -> SchedulingService:
    """Factory function to get scheduling service instance"""
    return SchedulingService(user_id)
