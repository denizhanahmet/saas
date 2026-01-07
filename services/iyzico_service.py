"""
Iyzico Payment Service - Subscription management with iyzico API
Uses official iyzipay SDK for reliable payment processing
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
    """Service for managing iyzico payments and subscriptions"""
    
    # Subscription plans
    PLANS = {
        'starter_monthly': {
            'id': 'starter_monthly',
            'name': 'Starter Aylık',
            'price': '99.00',
            'currency': 'TRY',
            'interval': 'monthly',
            'interval_count': 1,
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
            'monthly_equivalent': 82.50,
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
            'monthly_equivalent': 165.83,
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
    
    def __init__(self):
        self.api_key = os.getenv('IYZICO_API_KEY', '').strip()
        self.secret_key = os.getenv('IYZICO_SECRET_KEY', '').strip()
        base_url = os.getenv('IYZICO_BASE_URL', 'sandbox-api.iyzipay.com').strip()
        
        # Ensure proper URL format for iyzipay SDK
        if base_url.startswith('https://'):
            base_url = base_url.replace('https://', '')
        if base_url.startswith('http://'):
            base_url = base_url.replace('http://', '')
        
        self.base_url = base_url
        
        # iyzipay SDK options
        self.options = {
            'api_key': self.api_key,
            'secret_key': self.secret_key,
            'base_url': self.base_url
        }
        
        # Valid API key should be at least 30 chars
        valid_api_key = self.api_key and len(self.api_key) >= 30
        valid_secret_key = self.secret_key and len(self.secret_key) >= 30
        
        self.use_mock = not (valid_api_key and valid_secret_key)
        
        if self.use_mock:
            logger.warning("Iyzico API keys not configured or invalid - using mock mode")
        else:
            logger.info(f"Iyzico configured with base_url: {self.base_url}")
    
    def _generate_random_string(self, length: int = 8) -> str:
        """Generate random string for conversation ID"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    def get_plan(self, plan_id: str) -> Optional[Dict]:
        """Get plan details by ID"""
        return self.PLANS.get(plan_id)
    
    def get_all_plans(self) -> Dict:
        """Get all available plans"""
        return self.PLANS
    
    def create_checkout_form(self, user_id: str, plan_id: str, 
                              buyer_info: Dict, callback_url: str) -> Dict[str, Any]:
        """
        Create iyzico checkout form for subscription payment
        """
        # Ensure user_id is string
        user_id = str(user_id)
        
        plan = self.get_plan(plan_id)
        if not plan:
            return {'status': 'error', 'message': 'Invalid plan'}
        
        # Use mock mode if API keys not properly configured
        if self.use_mock:
            return self._mock_checkout_form(user_id, plan_id, plan, callback_url)
        
        try:
            conversation_id = f"sub_{user_id}_{self._generate_random_string()}"
            
            # Prepare buyer
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
            
            # Address
            address = {
                'contactName': f"{buyer_info.get('first_name', '')} {buyer_info.get('last_name', '')}".strip() or 'Müşteri',
                'city': buyer_info.get('city', 'Istanbul'),
                'country': 'Turkey',
                'address': buyer_info.get('address', 'Türkiye'),
                'zipCode': '34000'
            }
            
            # Basket items
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
            
            # Request parameters
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
            
            # Use iyzipay SDK
            checkout_form_initialize = iyzipay.CheckoutFormInitialize().create(request, self.options)
            
            # SDK returns bytes, decode to JSON
            import json
            response_bytes = checkout_form_initialize.read()
            result = json.loads(response_bytes.decode('utf-8'))
            
            logger.info(f"Iyzico response status: {result.get('status')}")
            
            if result.get('status') == 'success':
                # Save pending subscription
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
        """Mock checkout form for testing without API keys"""
        conversation_id = f"mock_sub_{user_id}_{self._generate_random_string()}"
        token = f"mock_token_{self._generate_random_string(16)}"
        
        # Save pending subscription
        self._save_pending_subscription(user_id, plan_id, conversation_id, token)
        
        # Generate mock checkout form HTML
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
        """Save pending subscription to Firebase"""
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
        Verify payment after callback using iyzipay SDK
        """
        # Get pending subscription
        pending = get_data(f'pending_subscriptions/{token}')
        if not pending:
            return {'status': 'error', 'message': 'Invalid payment token'}
        
        # Check if mock mode
        if token.startswith('mock_token_'):
            return self._mock_verify_payment(pending)
        
        try:
            request = {
                'locale': 'tr',
                'conversationId': pending.get('conversation_id'),
                'token': token
            }
            
            # Use iyzipay SDK
            checkout_form_result = iyzipay.CheckoutForm().retrieve(request, self.options)
            
            # SDK returns bytes, decode to JSON
            import json
            response_bytes = checkout_form_result.read()
            result = json.loads(response_bytes.decode('utf-8'))
            
            logger.info(f"Payment verification result: status={result.get('status')}, paymentStatus={result.get('paymentStatus')}")
            
            if result.get('status') == 'success' and result.get('paymentStatus') == 'SUCCESS':
                # Activate subscription
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
        """Mock payment verification for testing"""
        self._activate_subscription(pending, {'paymentId': f"mock_payment_{self._generate_random_string()}"})
        return {
            'status': 'success',
            'payment_id': f"mock_payment_{self._generate_random_string()}",
            'plan_id': pending.get('plan_id'),
            'mock': True
        }
    
    def _activate_subscription(self, pending: Dict, payment_result: Dict):
        """Activate subscription after successful payment"""
        user_id = pending.get('user_id')
        plan_id = pending.get('plan_id')
        plan = self.get_plan(plan_id)
        
        if not plan:
            return
        
        # Calculate expiry date
        now = datetime.now()
        if plan['interval'] == 'monthly':
            expires_at = now + timedelta(days=30)
        else:  # yearly
            expires_at = now + timedelta(days=365)
        
        # Save subscription to user
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
        
        # Also activate user account
        update_data(f'users/{user_id}', {
            'subscription': subscription_data,
            'is_active': True
        })
        
        # Remove pending subscription
        token = pending.get('token')
        if token:
            from firebase_realtime import delete_data
            delete_data(f'pending_subscriptions/{token}')
        
        logger.info(f"Subscription activated for user {user_id}: {plan_id}")
    
    def get_user_subscription(self, user_id: str) -> Optional[Dict]:
        """Get user's current subscription"""
        user = get_data(f'users/{user_id}')
        if not user:
            return None
        
        subscription = user.get('subscription')
        if not subscription:
            return None
        
        # Check if expired
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
        """Cancel user's subscription"""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return {'status': 'error', 'message': 'Aktif abonelik bulunamadı'}
        
        # Update subscription status
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
        """Check if user has access to a feature based on subscription"""
        subscription = self.get_user_subscription(user_id)
        
        if not subscription or subscription.get('status') != 'active':
            return False
        
        plan_id = subscription.get('plan_id', '')
        
        # Feature access matrix
        pro_features = ['sms_notifications', 'waitlist', 'smart_scheduling', 'advanced_reports']
        
        if feature in pro_features:
            return 'pro' in plan_id
        
        return True  # Basic features available to all paid plans


def get_iyzico_service() -> IyzicoService:
    """Get iyzico service instance"""
    return IyzicoService()
