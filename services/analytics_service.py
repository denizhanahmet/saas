"""
Analytics Service - AI-Powered Dashboard Insights
Randevu verilerinden doluluk oranı tahmini, en çok tercih edilen saatler gibi analitik widget'lar.
"""
import logging
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any
import statistics

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    AI-powered analytics service for appointment insights.
    Uses historical data to predict future trends and provide actionable insights.
    """
    
    def __init__(self, user_id: str):
        self.user_id = str(user_id)
    
    def get_all_appointments(self) -> List[Dict]:
        """Get all appointments for this user"""
        from firebase_realtime import get_data
        
        all_appointments_data = get_data('appointments')
        
        # Handle both dict and list cases from Firebase
        if not all_appointments_data:
            return []
        
        if isinstance(all_appointments_data, list):
            # Convert list to dict with index as key
            all_appointments_data = {str(i): v for i, v in enumerate(all_appointments_data) if v is not None}
        
        if isinstance(all_appointments_data, dict):
            user_appointments = [
                apt for apt in all_appointments_data.values()
                if apt and str(apt.get('user_id')) == str(self.user_id)
            ]
        else:
            user_appointments = []
        
        return user_appointments
    
    def _parse_appointment_datetime(self, apt: Dict) -> Optional[Dict]:
        """Parse appointment date and time safely"""
        try:
            apt_date_str = apt.get('appointment_date')
            apt_time_str = apt.get('appointment_time')
            
            if not apt_date_str:
                return None
            
            apt_date = datetime.strptime(apt_date_str, '%Y-%m-%d').date()
            
            apt_time = None
            if apt_time_str:
                try:
                    apt_time = datetime.strptime(str(apt_time_str)[:5], '%H:%M').time()
                except:
                    pass
            
            return {
                'date': apt_date,
                'time': apt_time,
                'hour': apt_time.hour if apt_time else None,
                'weekday': apt_date.weekday(),
                'status': apt.get('status', 'scheduled'),
                'duration': apt.get('duration', 60)
            }
        except Exception as e:
            return None
    
    def get_occupancy_prediction(self, days_ahead: int = 7) -> Dict[str, Any]:
        """
        Predict occupancy rate for next N days based on historical patterns.
        Uses weighted average of similar days in history.
        """
        appointments = self.get_all_appointments()
        parsed_appointments = []
        
        for apt in appointments:
            parsed = self._parse_appointment_datetime(apt)
            if parsed:
                parsed_appointments.append(parsed)
        
        if not parsed_appointments:
            return {
                'prediction': 0,
                'confidence': 'low',
                'message': 'Yeterli veri yok',
                'trend': 'stable',
                'daily_predictions': []
            }
        
        # Get user's working hours to calculate max capacity
        from firebase_realtime import get_data
        user = get_data(f'users/{self.user_id}')
        working_hours = user.get('working_hours', {}) if user else {}
        
        # Calculate average appointments per day of week
        weekday_counts = defaultdict(list)
        today = date.today()
        
        for i in range(90):  # Look back 90 days
            check_date = today - timedelta(days=i)
            weekday = check_date.weekday()
            
            # Count appointments on this day
            count = sum(1 for p in parsed_appointments if p['date'] == check_date)
            weekday_counts[weekday].append(count)
        
        # Calculate averages and trends
        weekday_averages = {}
        for weekday, counts in weekday_counts.items():
            if counts:
                weekday_averages[weekday] = {
                    'avg': statistics.mean(counts),
                    'recent': statistics.mean(counts[-4:]) if len(counts) >= 4 else statistics.mean(counts),
                    'trend': 'up' if (statistics.mean(counts[-4:]) > statistics.mean(counts[:-4]) if len(counts) > 4 else statistics.mean(counts[-2:]) > statistics.mean(counts[:-2]) if len(counts) > 2 else True) else 'down' if (statistics.mean(counts[-2:]) < statistics.mean(counts[:-2]) if len(counts) > 2 else False) else 'stable'
                }
        
        # Generate predictions for next N days
        daily_predictions = []
        overall_trend = 'stable'
        
        for i in range(days_ahead):
            target_date = today + timedelta(days=i)
            target_weekday = target_date.weekday()
            
            # Skip if it's a blocked day
            blocked_days = get_data('blocked_days')
            
            # Handle both list and dict from Firebase
            is_blocked = False
            if blocked_days:
                if isinstance(blocked_days, list):
                    blocked_days = {str(i): v for i, v in enumerate(blocked_days) if v is not None}
                
                if isinstance(blocked_days, dict):
                    is_blocked = any(
                        bd.get('date') == target_date.strftime('%Y-%m-%d') and str(bd.get('user_id')) == self.user_id
                        for bd in blocked_days.values() if bd
                    )
            
            if is_blocked:
                daily_predictions.append({
                    'date': target_date.strftime('%Y-%m-%d'),
                    'day_name': self._get_day_name(target_weekday),
                    'predicted': 0,
                    'is_blocked': True
                })
                continue
            
            if target_weekday in weekday_averages:
                pred = weekday_averages[target_weekday]
                predicted = round(pred['avg'])
                trend = pred['trend']
            else:
                predicted = 1
                trend = 'stable'
            
            daily_predictions.append({
                'date': target_date.strftime('%Y-%m-%d'),
                'day_name': self._get_day_name(target_weekday),
                'predicted': predicted,
                'trend': trend,
                'is_blocked': False
            })
        
        # Calculate overall confidence
        total_appointments = len(parsed_appointments)
        if total_appointments > 50:
            confidence = 'high'
        elif total_appointments > 20:
            confidence = 'medium'
        else:
            confidence = 'low'
        
        # Calculate average occupancy
        avg_daily = statistics.mean([weekday_averages.get(w, {}).get('avg', 0) for w in range(7)])
        
        # Determine trend
        recent_avg = statistics.mean([
            weekday_averages.get(w, {}).get('recent', 0) 
            for w in range(7)
        ])
        
        if recent_avg > avg_daily * 1.1:
            overall_trend = 'up'
        elif recent_avg < avg_daily * 0.9:
            overall_trend = 'down'
        else:
            overall_trend = 'stable'
        
        return {
            'prediction': round(avg_daily),
            'confidence': confidence,
            'message': self._get_prediction_message(avg_daily, confidence),
            'trend': overall_trend,
            'daily_predictions': daily_predictions,
            'total_appointments': total_appointments
        }
    
    def _get_day_name(self, weekday: int) -> str:
        """Get Turkish day name"""
        days = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
        return days[weekday]
    
    def _get_prediction_message(self, avg: float, confidence: str) -> str:
        """Get human-readable prediction message"""
        if confidence == 'low':
            return 'Daha fazla veri toplamaya ihtiyacımız var'
        
        if avg < 1:
            return 'Günlük ortalama randevu sayısı çok düşük'
        elif avg < 3:
            return 'Orta seviye doluluk bekleniyor'
        elif avg < 5:
            return 'Yüksek doluluk oranı bekleniyor'
        else:
            return 'Çok yoğun bir dönem öngörülüyor'
    
    def get_most_preferred_hours(self) -> Dict[str, Any]:
        """
        Analyze which hours are most preferred by clients.
        Returns hourly distribution with insights.
        """
        appointments = self.get_all_appointments()
        parsed_appointments = []
        
        for apt in appointments:
            parsed = self._parse_appointment_datetime(apt)
            if parsed and parsed['hour'] is not None:
                parsed_appointments.append(parsed)
        
        if not parsed_appointments:
            return {
                'preferred_hours': [],
                'insight': 'Yeterli veri yok',
                'peak_hour': None,
                'off_peak_hours': []
            }
        
        # Count appointments per hour
        hour_counts = Counter()
        weekday_hour_counts = defaultdict(Counter)
        
        for apt in parsed_appointments:
            hour = apt['hour']
            weekday = apt['weekday']
            hour_counts[hour] += 1
            weekday_hour_counts[weekday][hour] += 1
        
        # Get top 5 preferred hours
        top_hours = hour_counts.most_common(5)
        
        preferred_hours = []
        for hour, count in top_hours:
            percentage = (count / len(parsed_appointments)) * 100
            preferred_hours.append({
                'hour': f'{hour:02d}:00',
                'count': count,
                'percentage': round(percentage, 1)
            })
        
        # Find peak hour
        peak_hour = top_hours[0][0] if top_hours else None
        
        # Find off-peak hours (8-9am, 6-8pm are typically off-peak)
        all_hours = set(range(8, 20))
        busy_hours = set([h for h, _ in top_hours[:3]])
        off_peak = sorted(all_hours - busy_hours)
        
        off_peak_hours = [f'{h:02d}:00' for h in off_peak[:3]]
        
        # Generate insight
        if peak_hour:
            if 9 <= peak_hour <= 11:
                insight = 'Müşteriler genellikle sabah saatlerini tercih ediyor'
            elif 14 <= peak_hour <= 16:
                insight = 'Müşteriler öğleden sonraki saatleri tercih ediyor'
            elif 17 <= peak_hour <= 19:
                insight = 'Müşteriler akşam saatlerini tercih ediyor'
            else:
                insight = f'En yoğun saat {peak_hour}:00'
        else:
            insight = 'Yoğunluk dağıtımı dengeli'
        
        return {
            'preferred_hours': preferred_hours,
            'insight': insight,
            'peak_hour': f'{peak_hour:02d}:00' if peak_hour else None,
            'off_peak_hours': off_peak_hours,
            'total_analyzed': len(parsed_appointments)
        }
    
    def get_weekday_distribution(self) -> Dict[str, Any]:
        """
        Analyze which days of the week are most popular.
        """
        appointments = self.get_all_appointments()
        parsed_appointments = []
        
        for apt in appointments:
            parsed = self._parse_appointment_datetime(apt)
            if parsed:
                parsed_appointments.append(parsed)
        
        if not parsed_appointments:
            return {
                'weekday_stats': [],
                'best_day': None,
                'worst_day': None
            }
        
        # Count by weekday
        weekday_names = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
        weekday_counts = Counter()
        
        for apt in parsed_appointments:
            weekday_counts[apt['weekday']] += 1
        
        weekday_stats = []
        for i, name in enumerate(weekday_names):
            count = weekday_counts[i]
            percentage = (count / len(parsed_appointments)) * 100 if parsed_appointments else 0
            weekday_stats.append({
                'day': name,
                'day_index': i,
                'count': count,
                'percentage': round(percentage, 1)
            })
        
        # Sort by count
        weekday_stats.sort(key=lambda x: x['count'], reverse=True)
        
        best_day = weekday_stats[0]['day'] if weekday_stats else None
        worst_day = weekday_stats[-1]['day'] if weekday_stats else None
        
        return {
            'weekday_stats': weekday_stats,
            'best_day': best_day,
            'worst_day': worst_day,
            'total': len(parsed_appointments)
        }
    
    def get_client_insights(self) -> Dict[str, Any]:
        """
        Analyze client behavior and provide insights.
        """
        appointments = self.get_all_appointments()
        
        # Count unique clients
        client_emails = set()
        client_phones = set()
        
        for apt in appointments:
            client_email = apt.get('client_email')
            if client_email:
                client_emails.add(str(client_email).lower())
            client_phone = apt.get('client_phone')
            if client_phone:
                client_phones.add(str(client_phone))
        
        # Calculate repeat rate
        email_counts = Counter()
        for apt in appointments:
            client_email = apt.get('client_email')
            if client_email:
                email_counts[str(client_email).lower()] += 1
        
        repeat_clients = sum(1 for count in email_counts.values() if count > 1)
        total_unique = len(email_counts)
        
        repeat_rate = (repeat_clients / total_unique * 100) if total_unique > 0 else 0
        
        # Top clients
        top_clients = []
        for email, count in email_counts.most_common(5):
            # Find latest appointment
            client_appointments = [a for a in appointments if a.get('client_email', '').lower() == email]
            if client_appointments:
                last_apt = max(client_appointments, key=lambda x: x.get('appointment_date', ''))
                top_clients.append({
                    'email': email,
                    'appointment_count': count,
                    'last_appointment': last_apt.get('appointment_date', '')
                })
        
        return {
            'total_unique_clients': total_unique,
            'repeat_clients': repeat_clients,
            'repeat_rate': round(repeat_rate, 1),
            'top_clients': top_clients
        }
    
    def get_completion_rate_trend(self) -> Dict[str, Any]:
        """
        Track completion rate over time and predict future success rate.
        """
        appointments = self.get_all_appointments()
        parsed_appointments = []
        
        for apt in appointments:
            parsed = self._parse_appointment_datetime(apt)
            if parsed:
                parsed_appointments.append(parsed)
        
        if not parsed_appointments:
            return {
                'current_rate': 0,
                'trend': 'stable',
                'prediction': 'Yeterli veri yok'
            }
        
        # Calculate by month
        monthly_stats = defaultdict(lambda: {'completed': 0, 'cancelled': 0, 'total': 0})
        
        for apt in parsed_appointments:
            month_key = apt['date'].strftime('%Y-%m')
            monthly_stats[month_key]['total'] += 1
            
            if apt['status'] == 'completed':
                monthly_stats[month_key]['completed'] += 1
            elif apt['status'] in ['cancelled', 'rejected']:
                monthly_stats[month_key]['cancelled'] += 1
        
        # Calculate rates
        rates = []
        for month in sorted(monthly_stats.keys()):
            stats = monthly_stats[month]
            rate = (stats['completed'] / stats['total'] * 100) if stats['total'] > 0 else 0
            rates.append({'month': month, 'rate': rate})
        
        # Get current rate (last month)
        current_rate = rates[-1]['rate'] if rates else 0
        
        # Determine trend
        if len(rates) >= 2:
            if rates[-1]['rate'] > rates[-2]['rate'] + 5:
                trend = 'up'
            elif rates[-1]['rate'] < rates[-2]['rate'] - 5:
                trend = 'down'
            else:
                trend = 'stable'
        else:
            trend = 'stable'
        
        # Prediction message
        if trend == 'up':
            prediction = 'Tamamlanma oranı artıyor'
        elif trend == 'down':
            prediction = 'İptal oranınızı azaltmaya çalışın'
        else:
            prediction = 'Oranlar stabil seyrediyor'
        
        return {
            'current_rate': round(current_rate, 1),
            'trend': trend,
            'prediction': prediction,
            'monthly_rates': rates[-6:] if len(rates) > 6 else rates
        }
    
    def get_dashboard_summary(self) -> Dict[str, Any]:
        """
        Get a comprehensive dashboard summary with all insights.
        """
        return {
            'occupancy': self.get_occupancy_prediction(),
            'preferred_hours': self.get_most_preferred_hours(),
            'weekday': self.get_weekday_distribution(),
            'clients': self.get_client_insights(),
            'completion': self.get_completion_rate_trend()
        }


def get_analytics_service(user_id: str) -> AnalyticsService:
    """Factory function to get analytics service instance"""
    return AnalyticsService(user_id)
