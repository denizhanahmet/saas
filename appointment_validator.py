from datetime import datetime
from firebase_realtime import get_data

class AppointmentValidator:
    @staticmethod
    def validate_work_hours(user_id, appointment_datetime):
        """
        Validates if the given appointment datetime is within the user's working hours.
        
        Args:
            user_id (str): The ID of the user (provider).
            appointment_datetime (datetime): The datetime object of the appointment.
            
        Returns:
            tuple: (is_valid (bool), message (str))
        """
        # 1. Firebase'den kullanıcı ayarlarını getir
        user_data = get_data(f'users/{user_id}')
        if not user_data:
            return False, "Kullanıcı bulunamadı."

        # 2. Çalışma saatlerini al (ayarlanmamışsa varsayılan 09:00-17:00)
        work_start_str = user_data.get('work_start_time', '09:00')
        work_end_str = user_data.get('work_end_time', '17:00')

        try:
            # 3. Saatleri ayrıştır (parse et)
            work_start = datetime.strptime(work_start_str, '%H:%M').time()
            work_end = datetime.strptime(work_end_str, '%H:%M').time()
            appt_time = appointment_datetime.time()
        except ValueError:
            return False, "Çalışma saati formatı hatalı."

        # 4. Kesin karşılaştırma
        if work_start <= appt_time < work_end:
            return True, "Randevu saati uygun."
        
        return False, f"Randevu saati çalışma saatleri ({work_start_str} - {work_end_str}) dışında."