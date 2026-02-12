# 🔒 SaaS Projesi — Siber Güvenlik Denetim Raporu

**Tarih:** 12 Şubat 2026  
**Kapsam:** Tüm routes, services, konfigürasyon ve template dosyaları  
**Yöntem:** Statik kod analizi (SAST) — OWASP Top 10 kontrol listesi

---

## Özet

| Seviye | Sayı | Açıklama |
|--------|------|----------|
| 🔴 Kritik | 2 | Hemen düzeltilmeli |
| 🟠 Yüksek | 3 | En kısa sürede düzeltilmeli |
| 🟡 Orta | 4 | Planlı sprint içinde ele alınmalı |
| 🟢 Düşük | 3 | İyileştirme önerisi |
| ✅ Uygun | 8 | Zaten doğru uygulanmış |

---

## 🔴 KRİTİK

### 1. IDOR — Randevu Onay/Red İşlemlerinde Sahiplik Kontrolü Yok

**Dosya:** [dashboard.py](file:///c:/Users/deniz/OneDrive/Masaüstü/saas/routes/dashboard.py#L825-L853)

```python
# dashboard.py — approve_appointment / reject_appointment
def approve_appointment(appointment_id):
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    # ❌ user_id kontrolü YOK — herhangi bir giriş yapmış kullanıcı
    #    başka kullanıcıların randevularını onaylayabilir/reddedebilir
    appointments = get_data('appointments') or {}
    appointment = appointments.get(appointment_id)
    if appointment:
        appointment['status'] = 'approved'
        set_data(f'appointments/{appointment_id}', appointment)
```

**Risk:** Giriş yapmış herhangi bir kullanıcı, appointment_id'yi tahmin ederek başka birinin randevusunu onaylayabilir veya reddedebilir.

**Çözüm:**
```python
def approve_appointment(appointment_id):
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))
    user_id = str(session.get('user_id'))
    appointments = get_data('appointments') or {}
    appointment = appointments.get(appointment_id)
    if not appointment or str(appointment.get('user_id')) != user_id:
        flash('Randevu bulunamadı veya erişim yetkiniz yok.', 'error')
        return redirect(url_for('dashboard.dashboard'))
    # ... devam
```

---

### 2. Webhook Doğrulama Eksik — İyzico Webhook İmza Kontrolü Yok

**Dosya:** [subscription.py](file:///c:/Users/deniz/OneDrive/Masaüstü/saas/routes/subscription.py#L270-L298)

```python
@subscription_bp.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    # ❌ Hiçbir imza/secret doğrulaması yok
    # Saldırgan sahte webhook gönderek abonelik durumunu manipüle edebilir
```

**Risk:** Herkes `/subscription/webhook` adresine sahte JSON POST göndererek abonelik durumlarını değiştirebilir.

**Çözüm:** İyzico'nun webhook imzası doğrulanmalı veya alternatif olarak gelen IP whitelist kontrolü yapılmalı.

---

## 🟠 YÜKSEK

### 3. SHA-256 Düz Hash ile Oturum Açma (Legacy Fallback)

**Dosya:** [auth.py](file:///c:/Users/deniz/OneDrive/Masaüstü/saas/routes/auth.py#L183-L197)

```python
# login() fonksiyonundaki SHA-256 fallback
password_hash = hashlib.sha256(password.encode()).hexdigest()
if user.get('password_hash') == password_hash:
    # ❌ Salt yok, iteration yok — rainbow table ile kırılır
```

**Risk:** Veritabanında SHA-256 ile hashlenmiş şifresi olan eski kullanıcılar, rainbow table saldırısına açıktır.

**Çözüm:** Giriş başarılı olduğunda şifreyi otomatik olarak bcrypt/PBKDF2'ye upgrade edin:
```python
if user.get('password_hash') == password_hash:
    # Başarılı giriş — şifreyi güvenli hash'e yükselt
    new_hash = generate_password_hash(password)
    update_data(f'users/{user_id}', {
        'password': new_hash,
        'password_hash': None  # Eski hash'i sil
    })
```

---

### 4. `admin_required` Dekoratörde `@wraps` Eksik

**Dosya:** [admin.py](file:///c:/Users/deniz/OneDrive/Masaüstü/saas/routes/admin.py#L8-L22)

```python
def admin_required(f):
    def decorated_function(*args, **kwargs):
        # ...
    decorated_function.__name__ = f.__name__  # ❌ Yalnız __name__ kopyalanıyor
    return decorated_function
```

**Risk:** `__module__`, `__doc__`, `__qualname__` kaybolur. Flask debug toolbar ve logging araçları yanlış fonksiyon adı gösterir. Potansiyel route çakışması riski.

**Çözüm:**
```python
from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # ...
    return decorated_function
```

---

### 5. Content-Security-Policy (CSP) Başlığı Eksik

**Dosya:** [wsqi.py](file:///c:/Users/deniz/OneDrive/Masaüstü/saas/wsqi.py#L182-L197)

Mevcut güvenlik başlıkları iyi (`X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`) ama CSP yok.

**Risk:** XSS açığı bulunursa, saldırgan external script yükleyebilir.

**Çözüm:**
```python
response.headers['Content-Security-Policy'] = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self'"
)
```

---

## 🟡 ORTA

### 6. Hata Mesajlarında Detay Sızıntısı

**Birçok dosyada:**
```python
flash(f'Hata oluştu: {str(e)}', 'error')  # ❌ Exception detayı kullanıcıya gösteriliyor
```

**Risk:** Stack trace, dosya yolları, veritabanı bilgileri kullanıcıya sızabilir.

**Çözüm:** Kullanıcıya genel mesaj gösterin, detayı sadece loglayın:
```python
import logging
logging.exception("Randevu güncelleme hatası")
flash('Bir hata oluştu. Lütfen tekrar deneyin.', 'error')
```

---

### 7. Sequential (Tahmin Edilebilir) Appointment ID'ler

**Dosya:** [appointments.py](file:///c:/Users/deniz/OneDrive/Masaüstü/saas/routes/appointments.py#L553)

```python
new_id = max([int(k) for k in all_appointments_data.keys()], default=0) + 1
# ❌ Ardışık sayı — IDOR saldırısında ID tahminini kolaylaştırır
```

**Risk:** Saldırgan `1, 2, 3, 4...` diye deneyerek tüm randevulara erişmeye çalışabilir. (#1 IDOR açığı ile birleşince ciddi risk)

**Çözüm:** UUID kullanın:
```python
import uuid
new_id = str(uuid.uuid4())
```

---

### 8. Rate Limiting Public Form'da Yetersiz

**Dosya:** [appointments.py](file:///c:/Users/deniz/OneDrive/Masaüstü/saas/routes/appointments.py#L472-L577)

Public randevu formu (`/r/<unique_link>`) için endpoint-spesifik rate limit tanımlanmamış. Global limit (1000/gün) spam saldırısını engellemek için yetersiz.

**Çözüm:**
```python
@appointments_bp.route('/r/<unique_link>', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def public_appointment_request(unique_link):
```

---

### 9. `checkout_form | safe` — Potansiyel XSS

**Dosya:** [checkout.html](file:///c:/Users/deniz/OneDrive/Masaüstü/saas/templates/subscription/checkout.html#L62)

```html
{{ checkout_form | safe }}
```

Bu değer iyzico SDK'sinden geliyor ve güvenilir bir kaynaktır. Ancak `| safe` filtresi auto-escaping'i devre dışı bırakır. İyzico API yanıtı manipüle edilirse (MITM saldırısı vb.) XSS oluşabilir.

**Risk:** Düşük (kaynak güvenilir) ama prensip olarak `| safe` kullanımı minimize edilmeli.

**Öneri:** HTTPS zorunluluğu ile MITM riski zaten düşük. Ek koruma için CSP başlığı (#5) eklenmelidir.

---

## 🟢 DÜŞÜK

### 10. Session Lifetime Çok Uzun (30 Gün)

**Dosya:** [wsqi.py](file:///c:/Users/deniz/OneDrive/Masaüstü/saas/wsqi.py#L129)

```python
app.config['PERMANENT_SESSION_LIFETIME'] = 30 * 24 * 3600  # 30 gün
```

**Öneri:** Kritik olmayan bir SaaS için kabul edilebilir, ama 7 gün daha güvenli olur. Ayrıca "Beni hatırla" checkbox'ı ile kullanıcıya seçme hakkı verilebilir.

---

### 11. `host='0.0.0.0'` ile Bind

**Dosya:** [wsqi.py](file:///c:/Users/deniz/OneDrive/Masaüstü/saas/wsqi.py#L354)

```python
app.run(debug=debug_mode, host='0.0.0.0', port=5000)
```

Development'ta tüm ağ arayüzlerinden erişime açıktır. Production'da bu, reverse proxy (nginx) arkasında olmalıdır.

**Öneri:** Development'ta `127.0.0.1`, production'da reverse proxy kullanın.

---

### 12. Firebase Realtime Database Kuralları

Firebase Security Rules dosyası incelenmedi (konsol üzerinden kontrol gerekli). Eğer kurallar `".read": true, ".write": true` ise, tüm veriler dışarıdan erişime açıktır.

**Öneri:** Firebase konsolunda Security Rules'ı kontrol edin. Minimum olarak:
```json
{
  "rules": {
    ".read": "auth != null",
    ".write": "auth != null"
  }
}
```

---

## ✅ DOĞRU UYGULANAN GÜVENLİK ÖNLEMLERİ

| # | Kontrol | Durum | Dosya/Konum |
|---|---------|-------|-------------|
| 1 | **CSRF Koruması** | ✅ CSRFProtect aktif, tüm form'larda token var | `wsqi.py` L72 |
| 2 | **Session Cookie Güvenliği** | ✅ HttpOnly, SameSite=Lax, production'da Secure | `wsqi.py` L126-128 |
| 3 | **Güvenlik Başlıkları** | ✅ X-Frame-Options, X-Content-Type-Options, X-XSS-Protection | `wsqi.py` L184-192 |
| 4 | **Dosya Yükleme Güvenliği** | ✅ Extension whitelist + magic byte doğrulaması + UUID dosya adı | `auth.py` L586-640 |
| 5 | **Open Redirect Koruması** | ✅ `_is_safe_url()` ile düzeltildi | `auth.py` L23-32 |
| 6 | **SECRET_KEY Kontrolü** | ✅ Production'da zorunlu, development'ta uyarı + otomatik üretim | `wsqi.py` L107-118 |
| 7 | **Rate Limiting** | ✅ Global limitler (1000/gün, 200/saat) | `wsqi.py` L76-82 |
| 8 | **Tekli Oturum Kontrolü** | ✅ `session_token` ile çoklu oturum engelleniyor | `wsqi.py` L200-219 |
| 9 | **PBKDF2 Şifre Hashing** | ✅ 100K iteration, rastgele salt | `password_utils.py` |
| 10 | **Max Request Size** | ✅ 5 MB limit | `wsqi.py` L121 |
| 11 | **Admin Dashboard Cache-Control** | ✅ no-store, no-cache | `wsqi.py` L194-196 |
| 12 | **IDOR Koruması (Diğer Endpoint'ler)** | ✅ `view()`, `edit()`, `update_status()`, `remove_blocked_day()` user_id kontrolü yapıyor | `dashboard.py`, `appointments.py` |

---

## 🎯 Öncelik Sıralaması

| Sıra | Bulgu | Tahmini Efor |
|------|-------|-------------|
| 1 | IDOR — approve/reject sahiplik kontrolü | 15 dk |
| 2 | Webhook imza doğrulama | 30 dk |
| 3 | SHA-256 → bcrypt auto-upgrade | 20 dk |
| 4 | `admin_required` → `@wraps` | 2 dk |
| 5 | CSP başlığı ekleme | 15 dk |
| 6 | Hata mesajı sanitizasyonu | 30 dk |
| 7 | Sequential ID → UUID | 15 dk |
| 8 | Public form rate limit | 5 dk |

> **Toplam Tahmini:** ~2.5 saat ile tüm kritik ve yüksek seviye bulgular kapatılabilir.
