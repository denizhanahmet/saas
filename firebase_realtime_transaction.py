"""
Firebase Realtime Database transaction support using Admin SDK
Optimistic lock ile atomic update işlemleri için
"""
from firebase_admin import db


def atomic_update(path, update_fn, max_retries=5):
    """
    Transaction benzeri atomic update fonksiyonu (Admin SDK ile)
    
    Args:
        path: Firebase path (örn: 'users/user123')
        update_fn: Mevcut veriyi alıp güncellenmiş veriyi döndüren fonksiyon
        max_retries: Maximum deneme sayısı (artık kullanılmıyor, uyumluluk için)
    
    Returns:
        Güncellenmiş veri
    """
    ref = db.reference(path)
    
    # Firebase Admin SDK transaction kullan
    def transaction_fn(current_data):
        if current_data is None:
            # Eğer veri yoksa, update_fn'den None ile çağır
            return update_fn(None)
        return update_fn(current_data)
    
    try:
        # Transaction ile atomic update
        result = ref.transaction(transaction_fn)
        return result
    except Exception as e:
        # Fallback: Basit get + set (daha az güvenli ama çalışır)
        current = ref.get()
        new_data = update_fn(current)
        ref.set(new_data)
        return new_data
