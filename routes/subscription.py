"""
Subscription Routes - Payment and subscription management
"""
import logging
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for, jsonify
from flask_wtf.csrf import CSRFProtect

from firebase_realtime import get_data, update_data
from services.iyzico_service import get_iyzico_service

logger = logging.getLogger(__name__)

subscription_bp = Blueprint('subscription', __name__)


def login_required(f):
    """Require login for subscription routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Bu sayfaya erişmek için giriş yapmalısınız.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


@subscription_bp.route('/start-trial', methods=['POST'])
@login_required
def start_trial():
    """3 günlük ücretsiz deneme sürümünü başlat"""
    user_id = str(session['user_id'])
    user = get_data(f'users/{user_id}')
    
    if not user:
        return jsonify({'success': False, 'error': 'Kullanıcı bulunamadı'}), 404
    
    # Zaten trial veya aktif abonelik varsa engelle
    status = user.get('subscription_status', 'pending')
    if status in ('trial', 'active'):
        return jsonify({'success': False, 'error': 'Zaten aktif aboneliğiniz var'}), 400
    
    # Trial başlat
    trial_end = datetime.utcnow() + timedelta(days=3)
    update_data(f'users/{user_id}', {
        'subscription_status': 'trial',
        'trial_ends_at': trial_end.isoformat(),
        'trial_started_at': datetime.utcnow().isoformat()
    })
    
    # Türkçe tarih formatı
    months_tr = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
                 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']
    trial_end_local = trial_end + timedelta(hours=3)  # UTC+3
    formatted_date = f"{trial_end_local.day} {months_tr[trial_end_local.month - 1]} {trial_end_local.year}, {trial_end_local.strftime('%H:%M')}"
    
    return jsonify({
        'success': True,
        'trial_ends_at': trial_end.isoformat(),
        'trial_ends_formatted': formatted_date
    })


@subscription_bp.route('/trial-expired')
def trial_expired():
    """Trial süresi dolmuş kullanıcılar için uyarı sayfası"""
    iyzico = get_iyzico_service()
    plans = iyzico.get_all_plans()
    
    # Kullanıcı bilgilerini al
    trial_info = None
    if session.get('user_id'):
        user = get_data(f"users/{session['user_id']}")
        if user:
            trial_info = {
                'trial_ends_at': user.get('trial_ends_at'),
                'subscription_status': user.get('subscription_status', 'expired')
            }
    
    return render_template('subscription/trial_expired.html',
                           plans=plans,
                           trial_info=trial_info)


@subscription_bp.route('/pricing')
def pricing():
    """Public pricing page"""
    iyzico = get_iyzico_service()
    plans = iyzico.get_all_plans()
    
    # Check if user is logged in and has subscription
    current_plan = None
    user_status = None
    if session.get('user_id'):
        subscription = iyzico.get_user_subscription(str(session['user_id']))
        if subscription:
            current_plan = subscription.get('plan_id')
        user = get_data(f"users/{session['user_id']}")
        if user:
            user_status = user.get('subscription_status', 'pending')
    
    return render_template('subscription/pricing.html',
                           plans=plans,
                           current_plan=current_plan,
                           user_status=user_status)


@subscription_bp.route('/checkout/<plan_id>')
@login_required
def checkout(plan_id):
    """Checkout page for a specific plan"""
    iyzico = get_iyzico_service()
    plan = iyzico.get_plan(plan_id)
    
    if not plan:
        flash('Geçersiz plan.', 'error')
        return redirect(url_for('subscription.pricing'))
    
    # Get user info
    user_id = str(session['user_id'])
    user = get_data(f'users/{user_id}')
    
    if not user:
        flash('Kullanıcı bulunamadı.', 'error')
        return redirect(url_for('subscription.pricing'))
    
    # Prepare buyer info
    buyer_info = {
        'first_name': user.get('first_name', ''),
        'last_name': user.get('last_name', ''),
        'email': user.get('email', ''),
        'phone': user.get('phone', '+905000000000'),
        'address': user.get('address', 'Türkiye'),
        'city': user.get('city', 'Istanbul'),
        'identity_number': '11111111111',  # Required by iyzico
        'ip': request.remote_addr or '127.0.0.1'
    }
    
    # Create callback URL
    callback_url = url_for('subscription.callback', _external=True)
    
    # Create checkout form
    result = iyzico.create_checkout_form(user_id, plan_id, buyer_info, callback_url)
    
    if result.get('status') != 'success':
        flash(result.get('message', 'Ödeme formu oluşturulamadı.'), 'error')
        return redirect(url_for('subscription.pricing'))
    
    return render_template('subscription/checkout.html',
                           plan=plan,
                           checkout_form=result.get('checkoutFormContent'),
                           token=result.get('token'))


@subscription_bp.route('/callback', methods=['GET', 'POST'])
def callback():
    """Handle iyzico callback after payment - CSRF exempt for external POST"""
    # iyzico sends POST with form data, token is in request form
    if request.method == 'POST':
        token = request.form.get('token')
    else:
        token = request.args.get('token')
    
    if not token:
        flash('Geçersiz ödeme işlemi.', 'error')
        return redirect(url_for('subscription.pricing'))
    
    iyzico = get_iyzico_service()
    result = iyzico.verify_payment(token)
    
    if result.get('status') == 'success':
        flash('Ödemeniz başarıyla tamamlandı! Aboneliğiniz aktif.', 'success')
        return redirect(url_for('subscription.success', plan_id=result.get('plan_id')))
    else:
        flash(result.get('message', 'Ödeme doğrulanamadı.'), 'error')
        return redirect(url_for('subscription.pricing'))


@subscription_bp.route('/success/<plan_id>')
@login_required
def success(plan_id):
    """Payment success page"""
    iyzico = get_iyzico_service()
    plan = iyzico.get_plan(plan_id)
    subscription = iyzico.get_user_subscription(str(session['user_id']))
    
    return render_template('subscription/success.html',
                           plan=plan,
                           subscription=subscription)


@subscription_bp.route('/manage')
@login_required
def manage():
    """Subscription management page"""
    user_id = str(session['user_id'])
    iyzico = get_iyzico_service()
    
    subscription = iyzico.get_user_subscription(user_id)
    current_plan = None
    
    if subscription:
        current_plan = iyzico.get_plan(subscription.get('plan_id'))
    
    all_plans = iyzico.get_all_plans()
    
    return render_template('subscription/manage.html',
                           subscription=subscription,
                           current_plan=current_plan,
                           all_plans=all_plans)


@subscription_bp.route('/cancel', methods=['POST'])
@login_required
def cancel():
    """Cancel subscription"""
    user_id = str(session['user_id'])
    iyzico = get_iyzico_service()
    
    result = iyzico.cancel_subscription(user_id)
    
    if result.get('status') == 'success':
        flash(result.get('message'), 'success')
    else:
        flash(result.get('message'), 'error')
    
    return redirect(url_for('subscription.manage'))


# ==================
# API Endpoints
# ==================

@subscription_bp.route('/api/status')
@login_required
def api_status():
    """Get current subscription status"""
    user_id = str(session['user_id'])
    iyzico = get_iyzico_service()
    
    subscription = iyzico.get_user_subscription(user_id)
    
    return jsonify({
        'has_subscription': subscription is not None,
        'subscription': subscription
    })


@subscription_bp.route('/api/check-feature/<feature>')
@login_required
def api_check_feature(feature):
    """Check if user has access to a feature"""
    user_id = str(session['user_id'])
    iyzico = get_iyzico_service()
    
    has_access = iyzico.check_feature_access(user_id, feature)
    
    return jsonify({
        'feature': feature,
        'has_access': has_access
    })


# ==================
# Webhook Endpoint
# ==================

@subscription_bp.route('/webhook', methods=['POST'])
def webhook():
    """Handle iyzico webhook notifications"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'status': 'error', 'message': 'No data'}), 400
        
        event_type = data.get('eventType')
        
        logger.info(f"Iyzico webhook received: {event_type}")
        
        # Handle different event types
        if event_type == 'SUBSCRIPTION_PAYMENT_SUCCESS':
            # Renewal payment successful
            pass
        elif event_type == 'SUBSCRIPTION_PAYMENT_FAILED':
            # Renewal payment failed
            pass
        elif event_type == 'SUBSCRIPTION_CANCELLED':
            # Subscription cancelled
            pass
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
