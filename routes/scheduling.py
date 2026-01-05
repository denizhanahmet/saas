"""
Scheduling Routes - API endpoints for slot availability and suggestions
"""
import logging
from datetime import datetime, date
from functools import wraps

from flask import Blueprint, jsonify, request, session

from services.scheduling_service import get_scheduling_service

logger = logging.getLogger(__name__)

scheduling_bp = Blueprint('scheduling', __name__)


def login_required(f):
    """Require login for scheduling routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'error': 'Giriş yapmanız gerekiyor'}), 401
        return f(*args, **kwargs)
    return decorated_function


@scheduling_bp.route('/slots/<date_str>')
@login_required
def get_slots(date_str):
    """
    Get available slots for a specific date
    GET /api/slots/2026-01-10
    """
    user_id = str(session.get('user_id'))
    
    try:
        service = get_scheduling_service(user_id)
        result = service.get_slots_for_date_api(date_str)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting slots: {e}")
        return jsonify({'error': 'Slotlar alınamadı', 'slots': []}), 500


@scheduling_bp.route('/slots/<date_str>/instructor/<instructor_id>')
def get_instructor_slots(date_str, instructor_id):
    """
    Get available slots for a specific instructor (public endpoint)
    GET /api/slots/2026-01-10/instructor/abc123
    """
    try:
        service = get_scheduling_service(instructor_id)
        result = service.get_slots_for_date_api(date_str)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting instructor slots: {e}")
        return jsonify({'error': 'Slotlar alınamadı', 'slots': []}), 500


@scheduling_bp.route('/suggest', methods=['POST'])
@login_required
def suggest_slots():
    """
    Get slot suggestions based on preferences
    POST /api/suggest
    {
        "preferred_date": "2026-01-10",
        "duration": 60,
        "limit": 5
    }
    """
    user_id = str(session.get('user_id'))
    data = request.get_json() or {}
    
    preferred_date_str = data.get('preferred_date', datetime.now().strftime('%Y-%m-%d'))
    duration = data.get('duration', 60)
    limit = min(data.get('limit', 5), 10)  # Max 10 suggestions
    
    try:
        preferred_date = datetime.strptime(preferred_date_str, '%Y-%m-%d').date()
    except ValueError:
        preferred_date = date.today()
    
    try:
        service = get_scheduling_service(user_id)
        suggestions = service.suggest_slots(preferred_date, duration, limit)
        
        return jsonify({
            'suggestions': suggestions,
            'count': len(suggestions),
            'settings': service.settings
        })
    except Exception as e:
        logger.error(f"Error suggesting slots: {e}")
        return jsonify({'error': 'Öneriler alınamadı', 'suggestions': []}), 500


@scheduling_bp.route('/suggest/instructor/<instructor_id>', methods=['POST'])
def suggest_instructor_slots(instructor_id):
    """
    Get slot suggestions for a specific instructor (public endpoint)
    """
    data = request.get_json() or {}
    
    preferred_date_str = data.get('preferred_date', datetime.now().strftime('%Y-%m-%d'))
    duration = data.get('duration', 60)
    limit = min(data.get('limit', 5), 10)
    
    try:
        preferred_date = datetime.strptime(preferred_date_str, '%Y-%m-%d').date()
    except ValueError:
        preferred_date = date.today()
    
    try:
        service = get_scheduling_service(instructor_id)
        suggestions = service.suggest_slots(preferred_date, duration, limit)
        
        return jsonify({
            'suggestions': suggestions,
            'count': len(suggestions)
        })
    except Exception as e:
        logger.error(f"Error suggesting instructor slots: {e}")
        return jsonify({'error': 'Öneriler alınamadı', 'suggestions': []}), 500


@scheduling_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def scheduling_settings():
    """
    Get or update scheduling settings
    """
    user_id = str(session.get('user_id'))
    
    if request.method == 'GET':
        service = get_scheduling_service(user_id)
        return jsonify({
            'settings': service.settings
        })
    
    # POST - Update settings
    from firebase_realtime import update_data
    
    data = request.get_json() or {}
    
    new_settings = {}
    
    if 'buffer_time' in data:
        new_settings['buffer_time'] = max(0, min(int(data['buffer_time']), 60))
    
    if 'min_advance_notice' in data:
        new_settings['min_advance_notice'] = max(0, min(int(data['min_advance_notice']), 168))
    
    if 'slot_duration' in data:
        new_settings['slot_duration'] = max(15, min(int(data['slot_duration']), 480))
    
    if new_settings:
        update_data(f'users/{user_id}/scheduling_settings', new_settings)
        logger.info(f"Updated scheduling settings for user {user_id}")
    
    return jsonify({
        'success': True,
        'settings': new_settings
    })
