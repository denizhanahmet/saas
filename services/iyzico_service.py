"""
Iyzico Ödeme Servisi - iyzico API ile abonelik yönetimi
iyzipay SDK kullanılarak güvenilir ödeme işleme
"""
import logging
import os
import random
import string
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import iyzipay

from firebase_realtime import get_data, set_data, update_data

logger = logging.getLogger(__name__)


class IyzicoService:
    """iyzico ödemeleri ve abonelikleri yönetmek için servis sınıfı"""
    
    # Varsayılan planlar — Firebase boşsa bu değerlerle seed'lenir
    DEFAULT_PLANS = {
        'starter_monthly': {
            'id': 'starter_monthly',
            'name': 'Starter Aylık',
            'price': '99.00',
            'currency': 'TRY',
            'interval': 'monthly',
            'interval_count': 1,
            'tier': 'starter',
            'features': [
                '50 Randevu/ay',
                'E-posta bildirimleri',
                'Temel raporlar',
                '1 Kullanıcı'
            ]
        },
        'starter_yearly': {
            'id': 'starter_yearly',
            'name': 'Starter Yıllık',
            'price': '990.00',
            'currency': 'TRY',
            'interval': 'yearly',
            'interval_count': 1,
            'tier': 'starter',
            'features': [
                '50 Randevu/ay',
                'E-posta bildirimleri',
                'Temel raporlar',
                '1 Kullanıcı',
                '2 ay ücretsiz'
            ]
        },
        'pro_monthly': {
            'id': 'pro_monthly',
            'name': 'Pro Aylık',
            'price': '199.00',
            'currency': 'TRY',
            'interval': 'monthly',
            'interval_count': 1,
            'tier': 'pro',
            'features': [
                'Sınırsız randevu',
                'E-posta + SMS bildirimleri',
                'Gelişmiş raporlar',
                'Bekleme listesi',
                'Akıllı zamanlama',
                '5 Kullanıcı'
            ]
        },
        'pro_yearly': {
            'id': 'pro_yearly',
            'name': 'Pro Yıllık',
            'price': '1990.00',
            'currency': 'TRY',
            'interval': 'yearly',
            'interval_count': 1,
            'tier': 'pro',
            'features': [
                'Sınırsız randevu',
                'E-posta + SMS bildirimleri',
                'Gelişmiş raporlar',
                'Bekleme listesi',
                'Akıllı zamanlama',
                '5 Kullanıcı',
                '2 ay ücretsiz'
            ]
        }
    }
    
    # Bellek içi cache — her instance'da yenilenir
    _plans_cache = None
    _plans_cache_time = None
    CACHE_TTL = 300  # 5 dakika
    
    def __init__(self):
        self.api_key = os.getenv('IYZICO_API_KEY', '').strip()
        self.secret_key = os.getenv('IYZICO_SECRET_KEY', '').strip()
        base_url = os.getenv('IYZICO_BASE_URL', 'sandbox-api.iyzipay.com').strip()
        
        # iyzipay SDK için uygun URL formatını sağla
        if base_url.startswith('https://'):
            base_url = base_url.replace('https://', '')
        if base_url.startswith('http://'):
            base_url = base_url.replace('http://', '')
        
        self.base_url = base_url
        
        # iyzipay SDK ayarları
        self.options = {
            'api_key': self.api_key,
            'secret_key': self.secret_key,
            'base_url': self.base_url
        }
        
        # Geçerli API key en az 30 karakter olmalı
        valid_api_key = self.api_key and len(self.api_key) >= 30
        valid_secret_key = self.secret_key and len(self.secret_key) >= 30
        
        self.use_mock = not (valid_api_key and valid_secret_key)
        
        if self.use_mock:
            logger.warning("Iyzico API keys not configured or invalid - using mock mode")
        else:
            logger.info(f"Iyzico configured with base_url: {self.base_url}")
    
    def _generate_random_string(self, length: int = 8) -> str:
        """Conversation ID için rastgele string oluştur"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    def _get_plans_from_firebase(self) -> Dict:
        """Firebase'den planları getir, yoksa default'ları seed'le"""
        now = datetime.now()
        
        # Cache kontrolü
        if (IyzicoService._plans_cache is not None and 
            IyzicoService._plans_cache_time is not None and
            (now - IyzicoService._plans_cache_time).total_seconds() < self.CACHE_TTL):
            return IyzicoService._plans_cache
        
        try:
            plans = get_data('plans')
            if not plans:
                # Firebase boş — default planları seed'le
                logger.info("Firebase'de plan bulunamadı, varsayılan planlar oluşturuluyor...")
                set_data('plans', self.DEFAULT_PLANS)
                plans = self.DEFAULT_PLANS.copy()
            
            IyzicoService._plans_cache = plans
            IyzicoService._plans_cache_time = now
            return plans
        except Exception as e:
            logger.error(f"Firebase plan okuma hatası: {e}")
            # Hata durumunda cache veya default kullan
            if IyzicoService._plans_cache:
                return IyzicoService._plans_cache
            return self.DEFAULT_PLANS.copy()
    
    @classmethod
    def invalidate_cache(cls):
        """Plan cache'ini temizle — admin güncelleme sonrası çağrılır"""
        cls._plans_cache = None
        cls._plans_cache_time = None
    
    def get_plan(self, plan_id: str) -> Optional[Dict]:
        """ID'ye göre plan detaylarını getir"""
        plans = self._get_plans_from_firebase()
        return plans.get(plan_id)
    
    def get_all_plans(self) -> Dict:
        """Tüm mevcut planları getir"""
        return self._get_plans_from_firebase()
    
    def update_plan(self, plan_id: str, updates: Dict) -> Dict:
        """Plan fiyat/özelliklerini güncelle (SuperAdmin)"""
        plans = self._get_plans_from_firebase()
        if plan_id not in plans:
            return {'status': 'error', 'message': 'Plan bulunamadı'}
        
        # Güncellenebilir alanlar
        allowed_fields = {'price', 'name', 'features'}
        filtered = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not filtered:
            return {'status': 'error', 'message': 'Güncellenecek alan bulunamadı'}
        
        # Fiyat formatı doğrulama
        if 'price' in filtered:
            try:
                price_val = float(filtered['price'])
                if price_val <= 0:
                    return {'status': 'error', 'message': 'Fiyat 0\'dan büyük olmalı'}
                filtered['price'] = f"{price_val:.2f}"
            except (ValueError, TypeError):
                return {'status': 'error', 'message': 'Geçersiz fiyat formatı'}
        
        filtered['updated_at'] = datetime.now().isoformat()
        
        try:
            update_data(f'plans/{plan_id}', filtered)
            self.invalidate_cache()
            logger.info(f"Plan güncellendi: {plan_id} -> {filtered}")
            return {'status': 'success', 'message': 'Plan başarıyla güncellendi'}
        except Exception as e:
            logger.error(f"Plan güncelleme hatası: {e}")
            return {'status': 'error', 'message': 'Güncelleme sırasında hata oluştu'}
    
    def create_checkout_form(self, user_id: str, plan_id: str, 
                              buyer_info: Dict, callback_url: str) -> Dict[str, Any]:
        """
        Abonelik ödemesi için iyzico ödeme formu oluştur
        """
        # user_id'nin string olduğundan emin ol
        user_id = str(user_id)
        
        plan = self.get_plan(plan_id)
        if not plan:
            return {'status': 'error', 'message': 'Invalid plan'}
        
        # API anahtarları düzgün yapılandırılmamışsa mock mod kullan
        if self.use_mock:
            return self._mock_checkout_form(user_id, plan_id, plan, callback_url)
        
        try:
            conversation_id = f"sub_{user_id}_{self._generate_random_string()}"
            
            # Alıcı bilgilerini hazırla
            buyer = {
                'id': str(user_id),
                'name': buyer_info.get('first_name', 'Ad'),
                'surname': buyer_info.get('last_name', 'Soyad'),
                'gsmNumber': buyer_info.get('phone', '+905000000000'),
                'email': buyer_info.get('email', 'test@test.com'),
                'identityNumber': buyer_info.get('identity_number', '11111111111'),
                'registrationAddress': buyer_info.get('address', 'Türkiye'),
                'ip': buyer_info.get('ip', '127.0.0.1'),
                'city': buyer_info.get('city', 'Istanbul'),
                'country': 'Turkey',
                'zipCode': '34000'
            }
            
            # Adres bilgileri
            address = {
                'contactName': f"{buyer_info.get('first_name', '')} {buyer_info.get('last_name', '')}".strip() or 'Müşteri',
                'city': buyer_info.get('city', 'Istanbul'),
                'country': 'Turkey',
                'address': buyer_info.get('address', 'Türkiye'),
                'zipCode': '34000'
            }
            
            # Sepet öğeleri
            basket_items = [
                {
                    'id': plan_id,
                    'name': plan['name'],
                    'category1': 'Abonelik',
                    'category2': plan['interval'].capitalize(),
                    'itemType': 'VIRTUAL',
                    'price': str(plan['price'])
                }
            ]
            
            # İstek parametreleri
            request = {
                'locale': 'tr',
                'conversationId': conversation_id,
                'price': str(plan['price']),
                'paidPrice': str(plan['price']),
                'currency': 'TRY',
                'basketId': f"basket_{user_id}_{plan_id}",
                'paymentGroup': 'SUBSCRIPTION',
                'callbackUrl': callback_url,
                'enabledInstallments': ['1'],
                'buyer': buyer,
                'shippingAddress': address,
                'billingAddress': address,
                'basketItems': basket_items
            }
            
            logger.info(f"Creating checkout form with conversation_id: {conversation_id}")
            
            # iyzipay SDK kullan
            checkout_form_initialize = iyzipay.CheckoutFormInitialize().create(request, self.options)
            
            # SDK bytes döndürür, JSON'a decode et
            import json
            response_bytes = checkout_form_initialize.read()
            result = json.loads(response_bytes.decode('utf-8'))
            
            logger.info(f"Iyzico response status: {result.get('status')}")
            
            if result.get('status') == 'success':
                # Bekleyen aboneliği kaydet
                self._save_pending_subscription(user_id, plan_id, conversation_id, result.get('token'))
                
                return {
                    'status': 'success',
                    'token': result.get('token'),
                    'checkoutFormContent': result.get('checkoutFormContent'),
                    'conversation_id': conversation_id
                }
            else:
                logger.error(f"Iyzico checkout form error: {result}")
                return {
                    'status': 'error',
                    'message': result.get('errorMessage', 'Ödeme formu oluşturulamadı'),
                    'error_code': result.get('errorCode')
                }
                
        except Exception as e:
            logger.error(f"Iyzico checkout form exception: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _mock_checkout_form(self, user_id: str, plan_id: str, plan: Dict, callback_url: str) -> Dict:
        """API anahtarları olmadan test için sahte ödeme formu oluştur"""
        conversation_id = f"mock_sub_{user_id}_{self._generate_random_string()}"
        token = f"mock_token_{self._generate_random_string(16)}"
        
        # Bekleyen aboneliği kaydet
        self._save_pending_subscription(user_id, plan_id, conversation_id, token)
        
        # Sahte ödeme formu HTML'i oluştur
        mock_form = f"""
        <div id="iyzipay-checkout-form" class="responsive">
            <div style="padding: 30px; background: linear-gradient(135deg, #f8f9fa, #e9ecef); border-radius: 16px; text-align: center; border: 2px dashed #dee2e6;">
                <h3 style="color: #333; margin-bottom: 20px;">🔒 Test Ödeme Formu</h3>
                <p style="color: #666; margin-bottom: 10px;">Plan: <strong>{plan['name']}</strong></p>
                <p style="color: #333; font-size: 24px; font-weight: bold; margin-bottom: 20px;">₺{plan['price']}</p>
                <p style="color: #dc3545; font-size: 12px; margin-bottom: 20px; padding: 10px; background: #fff3cd; border-radius: 8px;">
                    ⚠️ SANDBOX MODU - Gerçek ödeme alınmaz
                </p>
                <form action="{callback_url}" method="GET">
                    <input type="hidden" name="token" value="{token}">
                    <button type="submit" style="background: linear-gradient(135deg, #28a745, #20c997); 
                        color: white; padding: 15px 40px; border: none; border-radius: 8px; 
                        font-size: 16px; cursor: pointer; font-weight: bold; width: 100%;">
                        ✅ Ödemeyi Simüle Et
                    </button>
                </form>
            </div>
        </div>
        """
        
        return {
            'status': 'success',
            'token': token,
            'checkoutFormContent': mock_form,
            'conversation_id': conversation_id,
            'mock': True
        }
    
    def _save_pending_subscription(self, user_id: str, plan_id: str, 
                                    conversation_id: str, token: str):
        """Bekleyen aboneliği Firebase'e kaydet"""
        pending_data = {
            'user_id': user_id,
            'plan_id': plan_id,
            'conversation_id': conversation_id,
            'token': token,
            'status': 'pending',
            'created_at': datetime.now().isoformat()
        }
        set_data(f'pending_subscriptions/{token}', pending_data)
    
    def verify_payment(self, token: str) -> Dict[str, Any]:
        """
        iyzipay SDK kullanarak callback sonrası ödemeyi doğrula
        """
        # Bekleyen aboneliği getir
        pending = get_data(f'pending_subscriptions/{token}')
        if not pending:
            return {'status': 'error', 'message': 'Invalid payment token'}
        
        # Mock mod kontrolü
        if token.startswith('mock_token_'):
            return self._mock_verify_payment(pending)
        
        try:
            request = {
                'locale': 'tr',
                'conversationId': pending.get('conversation_id'),
                'token': token
            }
            
            # iyzipay SDK kullan
            checkout_form_result = iyzipay.CheckoutForm().retrieve(request, self.options)
            
            # SDK bytes döndürür, JSON'a decode et
            import json
            response_bytes = checkout_form_result.read()
            result = json.loads(response_bytes.decode('utf-8'))
            
            logger.info(f"Payment verification result: status={result.get('status')}, paymentStatus={result.get('paymentStatus')}")
            
            if result.get('status') == 'success' and result.get('paymentStatus') == 'SUCCESS':
                # Aboneliği aktifleştir
                self._activate_subscription(pending, result)
                return {
                    'status': 'success',
                    'payment_id': result.get('paymentId'),
                    'plan_id': pending.get('plan_id')
                }
            else:
                logger.error(f"Payment verification failed: {result}")
                return {
                    'status': 'error',
                    'message': result.get('errorMessage', 'Ödeme doğrulanamadı'),
                    'error_code': result.get('errorCode')
                }
                
        except Exception as e:
            logger.error(f"Payment verification error: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _mock_verify_payment(self, pending: Dict) -> Dict:
        """Test için sahte ödeme doğrulaması"""
        self._activate_subscription(pending, {'paymentId': f"mock_payment_{self._generate_random_string()}"})
        return {
            'status': 'success',
            'payment_id': f"mock_payment_{self._generate_random_string()}",
            'plan_id': pending.get('plan_id'),
            'mock': True
        }
    
    def _activate_subscription(self, pending: Dict, payment_result: Dict):
        """Başarılı ödeme sonrası aboneliği aktifleştir"""
        user_id = pending.get('user_id')
        plan_id = pending.get('plan_id')
        plan = self.get_plan(plan_id)
        
        if not plan:
            return
        
        # Bitiş tarihini hesapla
        now = datetime.now()
        if plan['interval'] == 'monthly':
            expires_at = now + timedelta(days=30)
        else:  # yearly
            expires_at = now + timedelta(days=365)
        
        # Aboneliği kullanıcıya kaydet
        subscription_data = {
            'plan_id': plan_id,
            'plan_name': plan['name'],
            'status': 'active',
            'starts_at': now.isoformat(),
            'expires_at': expires_at.isoformat(),
            'payment_id': payment_result.get('paymentId'),
            'last_payment_at': now.isoformat(),
            'auto_renew': True
        }
        
        # Kullanıcı hesabını da aktifleştir
        update_data(f'users/{user_id}', {
            'subscription': subscription_data,
            'is_active': True,
            'subscription_status': 'active'
        })
        
        # Bekleyen aboneliği sil
        token = pending.get('token')
        if token:
            from firebase_realtime import delete_data
            delete_data(f'pending_subscriptions/{token}')
        
        logger.info(f"Subscription activated for user {user_id}: {plan_id}")
    
    def get_user_subscription(self, user_id: str) -> Optional[Dict]:
        """Kullanıcının mevcut aboneliğini getir"""
        user = get_data(f'users/{user_id}')
        if not user:
            return None
        
        subscription = user.get('subscription')
        if not subscription:
            return None
        
        # Süresi dolmuş mu kontrol et
        expires_at = subscription.get('expires_at')
        if expires_at:
            try:
                expires = datetime.fromisoformat(expires_at)
                if datetime.now() > expires:
                    subscription['status'] = 'expired'
            except:
                pass
        
        return subscription
    
    def cancel_subscription(self, user_id: str) -> Dict:
        """Kullanıcının aboneliğini iptal et"""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return {'status': 'error', 'message': 'Aktif abonelik bulunamadı'}
        
        # Abonelik durumunu güncelle
        update_data(f'users/{user_id}/subscription', {
            'status': 'cancelled',
            'cancelled_at': datetime.now().isoformat(),
            'auto_renew': False
        })
        
        logger.info(f"Subscription cancelled for user {user_id}")
        
        return {
            'status': 'success',
            'message': 'Aboneliğiniz iptal edildi. Mevcut süreniz sonuna kadar kullanmaya devam edebilirsiniz.'
        }
    
    def check_feature_access(self, user_id: str, feature: str) -> bool:
        """Kullanıcının aboneliğine göre bir özelliğe erişimi olup olmadığını kontrol et"""
        subscription = self.get_user_subscription(user_id)
        
        if not subscription or subscription.get('status') != 'active':
            return False
        
        plan_id = subscription.get('plan_id', '')
        
        # Özellik erişim matrisi
        pro_features = ['sms_notifications', 'waitlist', 'smart_scheduling', 'advanced_reports']
        
        if feature in pro_features:
            return 'pro' in plan_id
        
        return True  # Temel özellikler tüm ücretli planlar için kullanılabilir


def get_iyzico_service() -> IyzicoService:
    """iyzico servis örneğini getir"""
    return IyzicoService()
