"""
Firebase Realtime Database integration using Admin SDK
Güvenli backend erişimi için Service Account kullanır
"""
import os
import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv

load_dotenv()

# Firebase Admin SDK'yı başlat (sadece bir kere)
if not firebase_admin._apps:
    # Service Account JSON dosyası
    cred_path = os.path.join(os.path.dirname(__file__), 'securityAccount.json')
    
    # Fallback: Environment variable'dan path al
    if not os.path.exists(cred_path):
        cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', cred_path)
    
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {
            'databaseURL': os.getenv('FIREBASE_DB_URL', 'https://saas-app-1dd97-default-rtdb.firebaseio.com')
        })
    else:
        raise FileNotFoundError(f"Firebase service account dosyası bulunamadı: {cred_path}")

# Temel CRUD fonksiyonları

def add_data(path, data):
    """Veri ekle (push) - otomatik ID oluşturur"""
    ref = db.reference(path)
    new_ref = ref.push(data)
    return {'name': new_ref.key}

def set_data(path, data):
    """Veri yaz (put) - belirtilen path'e doğrudan yazar"""
    ref = db.reference(path)
    ref.set(data)
    return data

def get_data(path):
    """Veri oku"""
    ref = db.reference(path)
    return ref.get()

def update_data(path, data):
    """Veri güncelle (patch) - mevcut veriyi korur, sadece belirtilen alanları günceller"""
    ref = db.reference(path)
    ref.update(data)
    return data

def delete_data(path):
    """Veri sil"""
    ref = db.reference(path)
    ref.delete()
    return None

# Örnek kullanım:
# add_data('users', {'username': 'ali', 'email': 'ali@example.com'})
# get_data('users')
