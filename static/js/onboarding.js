/**
 * Onboarding Wizard - Alpine.js Component
 * İlk kayıt olan kullanıcılar için adım adım rehber
 */
function onboardingWizard(uniqueLink) {
    return {
        currentStep: 0,
        totalSteps: 5,
        isVisible: true,
        isClosing: false,
        stepAnimClass: 'onboarding-active',
        uniqueLink: uniqueLink || '',

        steps: [
            {
                icon: 'waving_hand',
                iconColor: 'text-amber-500',
                iconBg: 'bg-amber-100 dark:bg-amber-900/30',
                title: 'Hoş Geldiniz! 🎉',
                description: 'Randevu Yönetim Sistemi\'ne hoş geldiniz! Bu kısa rehber, sistemi nasıl kullanacağınızı adım adım gösterecek.',
                details: [
                    'Randevularınızı kolayca yönetin',
                    'Müşterilerinize benzersiz randevu linki paylaşın',
                    'Takvim ve istatistiklerle işinizi takip edin'
                ]
            },
            {
                icon: 'add_circle',
                iconColor: 'text-blue-500',
                iconBg: 'bg-blue-100 dark:bg-blue-900/30',
                title: 'Randevu Oluşturma',
                description: 'Panel üzerinden "Yeni Randevu" butonuna tıklayarak hızlıca randevu oluşturabilirsiniz.',
                details: [
                    'Tarih, saat ve süre belirleyin',
                    'Müşteri bilgilerini girin',
                    'Otomatik çakışma kontrolü yapılır'
                ]
            },
            {
                icon: 'link',
                iconColor: 'text-purple-500',
                iconBg: 'bg-purple-100 dark:bg-purple-900/30',
                title: 'Benzersiz Randevu Linkiniz',
                description: 'Size özel bir randevu linkiniz var! Bu linki müşterilerinizle paylaşarak onların doğrudan randevu talep etmesini sağlayabilirsiniz.',
                details: [
                    'Linki sosyal medya veya mesajla paylaşın',
                    'Müşteriler uygun saatleri görebilir',
                    'Gelen talepler onayınıza sunulur'
                ]
            },
            {
                icon: 'insights',
                iconColor: 'text-emerald-500',
                iconBg: 'bg-emerald-100 dark:bg-emerald-900/30',
                title: 'Takvim & İstatistikler',
                description: 'Takvim görünümünde tüm randevularınızı bir bakışta görebilir, istatistikler sayfasında performansınızı takip edebilirsiniz.',
                details: [
                    'Aylık/haftalık takvim görünümü',
                    'Tamamlanma oranları ve trendler',
                    'En yoğun gün ve saatleriniz'
                ]
            },
            {
                icon: 'rocket_launch',
                iconColor: 'text-rose-500',
                iconBg: 'bg-rose-100 dark:bg-rose-900/30',
                title: 'Hazırsınız! 🚀',
                description: 'Artık sistemi kullanmaya başlayabilirsiniz. İlk randevunuzu oluşturarak hemen başlayın!',
                details: [
                    '3 günlük ücretsiz deneme süreniz başladı',
                    'Bloklu günler ekleyerek tatil günlerinizi belirleyin',
                    'Profil sayfanızdan çalışma saatlerinizi düzenleyin'
                ]
            }
        ],

        get progress() {
            return ((this.currentStep + 1) / this.totalSteps) * 100;
        },

        get isFirstStep() {
            return this.currentStep === 0;
        },

        get isLastStep() {
            return this.currentStep === this.totalSteps - 1;
        },

        nextStep() {
            if (this.currentStep < this.totalSteps - 1) {
                this.currentStep++;
            }
        },

        prevStep() {
            if (this.currentStep > 0) {
                this.currentStep--;
            }
        },

        goToStep(index) {
            if (index >= 0 && index < this.totalSteps) {
                this.currentStep = index;
            }
        },

        async completeOnboarding() {
            this.isClosing = true;

            try {
                // CSRF token al
                const csrfMeta = document.querySelector('meta[name="csrf-token"]');
                const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';

                const response = await fetch('/dashboard/complete-onboarding', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    credentials: 'same-origin'
                });

                const data = await response.json();
                if (!data.success) {
                    console.error('Onboarding tamamlama hatası:', data.error);
                }
            } catch (error) {
                console.error('Onboarding tamamlama hatası:', error);
            }

            // Animasyonlu kapanış
            setTimeout(() => {
                this.isVisible = false;
            }, 300);
        },

        skipOnboarding() {
            this.completeOnboarding();
        }
    };
}
