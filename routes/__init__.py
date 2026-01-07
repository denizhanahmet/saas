# Routes package
from .admin import admin_bp
from .appointments import appointments_bp
from .auth import auth_bp
from .dashboard import dashboard_bp
from .exports import exports_bp
from .scheduling import scheduling_bp
from .subscription import subscription_bp
from .waitlist import waitlist_bp

__all__ = ['auth_bp', 'appointments_bp', 'dashboard_bp', 'admin_bp', 
           'exports_bp', 'scheduling_bp', 'waitlist_bp', 'subscription_bp']


