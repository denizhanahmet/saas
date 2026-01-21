# 🗓️ Randevu Yönetim Sistemi (Appointment Management System)

Modern, kullanımı kolay ve güvenli randevu yönetim SaaS platformu.

A modern, easy-to-use and secure appointment management SaaS platform.

---

## 🇹🇷 Türkçe

### 📋 Özellikler

- **📅 Randevu Yönetimi** - Kolay randevu alma, düzenleme ve iptal
- **👥 Müşteri Yönetimi** - Müşteri bilgilerini kaydetme ve takip
- **📱 SMS Bildirimleri** - Twilio entegrasyonu ile otomatik SMS
- **📧 E-posta Bildirimleri** - Randevu hatırlatmaları
- **📊 Raporlar** - PDF ve CSV export
- **🔐 Güvenlik** - PBKDF2 şifreleme, CSRF koruması, Rate limiting
- **💳 Ödeme Sistemi** - iyzico entegrasyonu
- **🎨 Modern Arayüz** - Tailwind CSS ile responsive tasarım
- **🌙 Karanlık Mod** - Göz yormayan arayüz

### 🛠️ Teknolojiler

| Katman      | Teknoloji                      |
| ----------- | ------------------------------ |
| Backend     | Python, Flask                  |
| Veritabanı | Firebase Realtime Database     |
| Frontend    | HTML, Tailwind CSS, JavaScript |
| Ödeme      | iyzico                         |
| SMS         | Twilio                         |
| E-posta     | Flask-Mail (SMTP)              |

### ⚙️ Kurulum

1. **Repo'yu klonlayın:**

```bash
git clone https://github.com/denizhanahmet/saas.git
cd saas
```

2. **Sanal ortam oluşturun:**

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

3. **Bağımlılıkları yükleyin:**

```bash
pip install -r requirements.txt
```

4. **Ortam değişkenlerini ayarlayın:**

```bash
# .env dosyası oluşturun
SECRET_KEY=your-secret-key
MAIL_SERVER=smtp.gmail.com
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_PHONE_NUMBER=your-twilio-number
IYZICO_API_KEY=your-iyzico-key
IYZICO_SECRET_KEY=your-iyzico-secret
```

5. **Firebase yapılandırması:**

   - Firebase Console'dan Service Account JSON dosyasını indirin
   - `securityAccount.json` olarak kaydedin
6. **Uygulamayı çalıştırın:**

```bash
python wsqi.py
```

7. **Tarayıcıda açın:** http://localhost:5000

### 📁 Proje Yapısı

```
saas/
├── routes/              # API ve sayfa route'ları
│   ├── admin.py        # Admin paneli
│   ├── auth.py         # Kimlik doğrulama
│   ├── dashboard.py    # Kullanıcı paneli
│   ├── appointments.py # Randevu yönetimi
│   └── subscription.py # Abonelik yönetimi
├── services/           # İş mantığı servisleri
│   ├── iyzico_service.py
│   ├── sms_service.py
│   └── scheduler_service.py
├── templates/          # HTML şablonları
├── static/             # CSS, JS, resimler
└── wsqi.py             # Ana uygulama
```

### 💰 Abonelik Planları

| Plan     | Fiyat            | Özellikler         |
| -------- | ---------------- | ------------------- |
| Deneme   | 3 gün ücretsiz | Tüm özellikler    |
| Aylık   | 1.500 ₺/ay      | Sınırsız randevu |
| Yıllık | 15.000 ₺/yıl   | 2 ay ücretsiz      |

---

## 🇬🇧 English

### 📋 Features

- **📅 Appointment Management** - Easy booking, editing and cancellation
- **👥 Customer Management** - Store and track customer information
- **📱 SMS Notifications** - Automatic SMS via Twilio integration
- **📧 Email Notifications** - Appointment reminders
- **📊 Reports** - PDF and CSV export
- **🔐 Security** - PBKDF2 encryption, CSRF protection, Rate limiting
- **💳 Payment System** - iyzico integration
- **🎨 Modern UI** - Responsive design with Tailwind CSS
- **🌙 Dark Mode** - Eye-friendly interface

### 🛠️ Technologies

| Layer    | Technology                     |
| -------- | ------------------------------ |
| Backend  | Python, Flask                  |
| Database | Firebase Realtime Database     |
| Frontend | HTML, Tailwind CSS, JavaScript |
| Payment  | iyzico                         |
| SMS      | Twilio                         |
| Email    | Flask-Mail (SMTP)              |

### ⚙️ Installation

1. **Clone the repository:**

```bash
git clone https://github.com/denizhanahmet/saas.git
cd saas
```

2. **Create virtual environment:**

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

3. **Install dependencies:**

```bash
pip install -r requirements.txt
```

4. **Set environment variables:**

```bash
# Create .env file
SECRET_KEY=your-secret-key
MAIL_SERVER=smtp.gmail.com
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_PHONE_NUMBER=your-twilio-number
IYZICO_API_KEY=your-iyzico-key
IYZICO_SECRET_KEY=your-iyzico-secret
```

5. **Firebase configuration:**

   - Download Service Account JSON from Firebase Console
   - Save as `securityAccount.json`
6. **Run the application:**

```bash
python wsqi.py
```

7. **Open in browser:** http://localhost:5000

### 📁 Project Structure

```
saas/
├── routes/              # API and page routes
│   ├── admin.py        # Admin panel
│   ├── auth.py         # Authentication
│   ├── dashboard.py    # User dashboard
│   ├── appointments.py # Appointment management
│   └── subscription.py # Subscription management
├── services/           # Business logic services
│   ├── iyzico_service.py
│   ├── sms_service.py
│   └── scheduler_service.py
├── templates/          # HTML templates
├── static/             # CSS, JS, images
└── wsqi.py             # Main application
```

### 💰 Subscription Plans

| Plan    | Price       | Features               |
| ------- | ----------- | ---------------------- |
| Trial   | 3 days free | All features           |
| Monthly | ₺1,500/mo  | Unlimited appointments |
| Yearly  | ₺15,000/yr | 2 months free          |

---

## 📄 Lisans / License

MIT License

## 👤 Geliştirici / Developer

**Ahmet DENİZHAN**

---

⭐ Bu projeyi beğendiyseniz yıldız vermeyi unutmayın!

⭐ If you liked this project, don't forget to star it!
