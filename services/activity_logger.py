"""
Activity Logger Service
KVKK uyumlu sistem aktivite loglama servisi.
Kişisel veriler maskelenir, sadece anonimize veriler tutulur.
"""
import uuid
from datetime import datetime
from firebase_realtime import set_data, get_data


class ActivityLogger:
    """KVKK uyumlu aktivite loglama servisi"""
    
    # Action types
    LOGIN_SUCCESS = 'login_success'
    LOGIN_FAILED = 'login_failed'
    LOGOUT = 'logout'
    REGISTER = 'register'
    PASSWORD_CHANGE = 'password_change'
    PASSWORD_RESET = 'password_reset'
    
    APPOINTMENT_CREATE = 'appointment_create'
    APPOINTMENT_UPDATE = 'appointment_update'
    APPOINTMENT_APPROVE = 'appointment_approve'
    APPOINTMENT_REJECT = 'appointment_reject'
    APPOINTMENT_CANCEL = 'appointment_cancel'
    
    USER_STATUS_CHANGE = 'user_status_change'
    QUOTA_UPDATE = 'quota_update'
    PROFILE_UPDATE = 'profile_update'
    
    SMS_EVENT_CREATE = 'sms_event_create'
    SMS_EVENT_UPDATE = 'sms_event_update'
    SMS_EVENT_DELETE = 'sms_event_delete'
    SMS_SENT = 'sms_sent'
    
    WAITLIST_JOIN = 'waitlist_join'
    
    # Resource types
    RESOURCE_AUTH = 'auth'
    RESOURCE_APPOINTMENT = 'appointment'
    RESOURCE_USER = 'user'
    RESOURCE_SMS = 'sms'
    RESOURCE_WAITLIST = 'waitlist'
    
    @staticmethod
    def mask_ip(ip_address: str) -> str:
        """
        IP adresini KVKK için maskele.
        192.168.1.100 -> 192.168.*.*
        """
        if not ip_address:
            return '*.*.*.*'
        
        parts = ip_address.split('.')
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.*.*"
        return '*.*.*.*'
    
    @staticmethod
    def log_activity(
        user_id: str,
        action: str,
        resource: str,
        resource_id: str = None,
        details: str = None,
        ip_address: str = None,
        user_agent: str = None,
        success: bool = True
    ) -> dict:
        """
        Aktivite logu oluştur ve kaydet.
        
        Args:
            user_id: Kullanıcı ID (sadece referans, kişisel bilgi değil)
            action: Aksiyon tipi (login_success, appointment_create, etc.)
            resource: Kaynak tipi (auth, appointment, user, etc.)
            resource_id: Kaynak ID (optional)
            details: Detay mesajı (kişisel bilgi içermemeli)
            ip_address: IP adresi (maskelenecek)
            user_agent: Tarayıcı bilgisi
            success: İşlem başarılı mı
            
        Returns:
            Oluşturulan log kaydı
        """
        log_id = f"log_{uuid.uuid4().hex[:12]}"
        
        log_entry = {
            'id': log_id,
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id or 'anonymous',
            'action': action,
            'resource': resource,
            'resource_id': resource_id,
            'details': details,
            'ip_address': ActivityLogger.mask_ip(ip_address),
            'user_agent': user_agent[:200] if user_agent else None,  # Truncate for storage
            'success': success
        }
        
        try:
            set_data(f'activity_logs/{log_id}', log_entry)
        except Exception as e:
            # Log hatası kritik değil, sessizce devam et
            print(f"[ActivityLogger] Log kaydetme hatası: {e}")
        
        return log_entry
    
    @staticmethod
    def get_logs(
        limit: int = 50,
        action_filter: str = None,
        resource_filter: str = None,
        user_id_filter: str = None,
        start_date: str = None,
        end_date: str = None
    ) -> list:
        """
        Logları filtreli olarak getir.
        
        Args:
            limit: Maksimum kayıt sayısı
            action_filter: Aksiyon tipi filtresi
            resource_filter: Kaynak tipi filtresi
            user_id_filter: Kullanıcı ID filtresi
            start_date: Başlangıç tarihi (YYYY-MM-DD)
            end_date: Bitiş tarihi (YYYY-MM-DD)
            
        Returns:
            Log kayıtları listesi (yeniden eskiye)
        """
        logs = get_data('activity_logs') or {}
        logs_list = list(logs.values())
        
        # Filtreleme
        if action_filter:
            logs_list = [l for l in logs_list if l.get('action') == action_filter]
        
        if resource_filter:
            logs_list = [l for l in logs_list if l.get('resource') == resource_filter]
        
        if user_id_filter:
            logs_list = [l for l in logs_list if l.get('user_id') == user_id_filter]
        
        if start_date:
            logs_list = [l for l in logs_list if l.get('timestamp', '')[:10] >= start_date]
        
        if end_date:
            logs_list = [l for l in logs_list if l.get('timestamp', '')[:10] <= end_date]
        
        # Tarihe göre sırala (yeniden eskiye)
        logs_list = sorted(logs_list, key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Limit uygula
        return logs_list[:limit]
    
    @staticmethod
    def get_action_label(action: str) -> str:
        """Aksiyon için Türkçe etiket döndür"""
        labels = {
            'login_success': 'Başarılı Giriş',
            'login_failed': 'Başarısız Giriş',
            'logout': 'Çıkış',
            'register': 'Yeni Kayıt',
            'password_change': 'Şifre Değişikliği',
            'password_reset': 'Şifre Sıfırlama',
            'appointment_create': 'Randevu Oluşturma',
            'appointment_update': 'Randevu Güncelleme',
            'appointment_approve': 'Randevu Onaylama',
            'appointment_reject': 'Randevu Reddetme',
            'appointment_cancel': 'Randevu İptal',
            'user_status_change': 'Kullanıcı Durum Değişikliği',
            'quota_update': 'Kota Güncelleme',
            'profile_update': 'Profil Güncelleme',
            'sms_event_create': 'SMS Event Oluşturma',
            'sms_event_update': 'SMS Event Güncelleme',
            'sms_event_delete': 'SMS Event Silme',
            'sms_sent': 'SMS Gönderildi',
            'waitlist_join': 'Bekleme Listesine Katılım'
        }
        return labels.get(action, action)
    
    @staticmethod
    def get_resource_label(resource: str) -> str:
        """Kaynak için Türkçe etiket döndür"""
        labels = {
            'auth': 'Kimlik Doğrulama',
            'appointment': 'Randevu',
            'user': 'Kullanıcı',
            'sms': 'SMS',
            'waitlist': 'Bekleme Listesi'
        }
        return labels.get(resource, resource)
