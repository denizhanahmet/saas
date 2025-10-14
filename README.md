# Randevu Sistemi - Flask SaaS Uygulaması

Modern ve kullanıcı dostu bir randevu yönetim sistemi. Her kullanıcının kendi randevu tablosuna sahip olduğu, Flask tabanlı bir web uygulaması.

## 🚀 Özellikler

- **Kullanıcı Yönetimi**: Kayıt, giriş, profil yönetimi, şirket bilgileri
- **Randevu Yönetimi**: Oluşturma, düzenleme, silme, durum güncelleme
- **Müşteri Yönetimi**: Müşteri bilgileri, iletişim detayları, randevu geçmişi
- **Engellenmiş Günler**: Belirli tarihleri engelleme, tatil günleri yönetimi
- **SMS Yönetimi**: SMS gönderimi, kota takibi, gönderim logları
- **Dashboard**: Kullanıcıya özel istatistikler ve özet bilgiler
- **Çakışma Kontrolü**: Otomatik randevu çakışması tespiti
- **Responsive Tasarım**: Mobil uyumlu modern arayüz
- **Güvenlik**: Şifreli kimlik doğrulama ve veri koruması

## 🛠️ Teknolojiler

- **Backend**: Flask, SQLAlchemy, Flask-Login
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5
- **Veritabanı**: SQLite (geliştirme), PostgreSQL/MySQL (üretim)
- **Güvenlik**: Werkzeug şifreleme, CSRF koruması

## 📦 Kurulum

### 1. Projeyi İndirin
```bash
git clone <repository-url>
cd appointment-saas
```

### 2. Sanal Ortam Oluşturun
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# veya
venv\Scripts\activate     # Windows
```

### 3. Bağımlılıkları Yükleyin
```bash
pip install -r requirements.txt
```

### 4. Ortam Değişkenlerini Ayarlayın
```bash
cp env.example .env
# .env dosyasını düzenleyin
```

### 5. Veritabanını Güncelleyin (İlk Kurulum)
```bash
python migrate_database.py
```

### 6. Uygulamayı Çalıştırın
```bash
python app.py
```

Uygulama http://localhost:5000 adresinde çalışacaktır.

## 📁 Proje Yapısı

```
appointment-saas/
├── app.py                 # Ana uygulama dosyası
├── models.py              # Veritabanı modelleri (User, Appointment, Client, BlockedDay, SmsLog)
├── migrate_database.py    # Veritabanı güncelleme scripti
├── requirements.txt       # Python bağımlılıkları
├── routes/               # Route modülleri
│   ├── __init__.py
│   ├── auth.py           # Kimlik doğrulama
│   ├── appointments.py   # Randevu yönetimi
│   └── dashboard.py      # Dashboard
├── templates/            # HTML şablonları
│   ├── base.html
│   ├── index.html
│   ├── auth/
│   ├── dashboard/
│   └── appointments/
├── static/              # Statik dosyalar
│   ├── css/
│   └── js/
└── README.md
```

## 📊 Veritabanı Modelleri

### User (Kullanıcı)
- **Temel Bilgiler**: username, email, password, first_name, last_name, phone
- **Şirket Bilgileri**: company_name, logo_path
- **Yetkilendirme**: role, is_admin, is_active
- **SMS Yönetimi**: sms_quota (aylık SMS kotası)

### Appointment (Randevu)
- **Temel Bilgiler**: title, description, appointment_date, appointment_time, duration
- **İlişkiler**: user_id (kullanıcı), client_id (müşteri)
- **Durum Yönetimi**: status (scheduled, completed, cancelled)
- **Ek Bilgiler**: location, notes

### Client (Müşteri)
- **İletişim**: name, phone, email
- **İlişki**: user_id (hangi kullanıcıya ait)
- **Durum**: is_active, notes

### BlockedDay (Engellenmiş Gün)
- **Temel**: date, reason
- **İlişki**: user_id (hangi kullanıcı için engellenmiş)

### SmsLog (SMS Logu)
- **Mesaj**: message, timestamp
- **İlişkiler**: user_id (gönderen), client_id (alıcı)
- **Durum**: status (pending, sent, delivered, failed)
- **Maliyet**: cost, sms_provider

## 🔧 Konfigürasyon

### Veritabanı
Varsayılan olarak SQLite kullanılır. Üretim ortamında PostgreSQL veya MySQL önerilir:

```python
# PostgreSQL için
DATABASE_URL=postgresql://username:password@localhost/dbname

# MySQL için  
DATABASE_URL=mysql://username:password@localhost/dbname
```

### Güvenlik
`.env` dosyasında güçlü bir SECRET_KEY tanımlayın:

```bash
SECRET_KEY=your-super-secret-key-here
```

## 📱 Kullanım

### 1. Kayıt Olun
- Ana sayfadan "Kayıt Ol" butonuna tıklayın
- Gerekli bilgileri doldurun
- Hesabınız oluşturulacaktır

### 2. Randevu Oluşturun
- Dashboard'dan "Yeni Randevu" butonuna tıklayın
- Randevu detaylarını girin
- Çakışma kontrolü otomatik yapılır

### 3. Randevularınızı Yönetin
- "Randevularım" sayfasından tüm randevularınızı görün
- Filtreleme ve arama özelliklerini kullanın
- Randevuları düzenleyin veya silin

## 🔒 Güvenlik

- Şifreler bcrypt ile hash'lenir
- CSRF koruması aktif
- SQL injection koruması
- XSS koruması
- Güvenli oturum yönetimi

## 🚀 Üretim Dağıtımı

### Heroku
```bash
# Procfile oluşturun
echo "web: gunicorn app:app" > Procfile

# Heroku'ya deploy edin
heroku create your-app-name
git push heroku main
```

### Docker
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
```

## 🤝 Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Commit yapın (`git commit -m 'Add amazing feature'`)
4. Push yapın (`git push origin feature/amazing-feature`)
5. Pull Request açın

## 📄 Lisans

Bu proje MIT lisansı altında lisanslanmıştır.

## 📱 SMS Hatırlatma Sistemi

Uygulama, APScheduler kullanarak otomatik SMS hatırlatmaları gönderir.

### Özellikler
- **24 Saat Öncesi Hatırlatma**: Her onaylanmış randevu için 24 saat öncesinde otomatik SMS
- **Akıllı Zamanlama**: Randevu oluşturulduğunda, güncellendiğinde veya iptal edildiğinde otomatik zamanlama
- **Hata Yönetimi**: SMS gönderim hatalarında loglama ve kullanıcı bilgilendirme
- **Kota Yönetimi**: SMS kullanımı takibi ve kota kontrolü

### Konfigürasyon

`.env` dosyasına SMS ayarlarını ekleyin:

```bash
# SMS Configuration
SMS_API_KEY=your-sms-api-key-here
SMS_API_URL=https://api.sms-provider.com/send
SMS_SENDER_NAME=Randevu Sistemi
```

### SMS Servisi

SMS gönderimi için `services/sms_service.py` modülü kullanılır:

- **Geliştirme Modu**: SMS API anahtarı yoksa mock servis kullanılır
- **Üretim Modu**: Gerçek SMS API'si ile entegrasyon
- **Hata Yönetimi**: Başarısız gönderimler için loglama

### Zamanlayıcı Yönetimi

Scheduler servisi otomatik olarak:
- Uygulama başlatıldığında tüm bekleyen hatırlatmaları zamanlar
- Randevu oluşturulduğunda yeni hatırlatma ekler
- Randevu güncellendiğinde hatırlatmayı yeniden zamanlar
- Randevu iptal edildiğinde hatırlatmayı kaldırır

### Yönetim Komutları

```bash
# Zamanlanmış işleri listele
python manage_scheduler.py list

# Test hatırlatması zamanla
python manage_scheduler.py test

# Tüm hatırlatmaları kaldır
python manage_scheduler.py remove

# Tüm bekleyen hatırlatmaları yeniden zamanla
python manage_scheduler.py reschedule
```

### SMS Mesaj Formatı

```
Merhaba,

[Şirket Adı] ile [Randevu Başlığı] randevunuz yarın [Tarih] tarihinde [Saat] saatinde gerçekleşecektir.

Randevu detayları:
- Tarih: [Tarih]
- Saat: [Saat]
- Konu: [Randevu Başlığı]

Randevunuzu iptal etmek veya değiştirmek için lütfen bizimle iletişime geçin.

İyi günler,
[Şirket Adı]
```

## 📞 Destek

Sorularınız için issue açabilir veya iletişime geçebilirsiniz.

---

**Not**: Bu uygulama eğitim amaçlı geliştirilmiştir. Üretim ortamında kullanmadan önce güvenlik testlerini yapın.
