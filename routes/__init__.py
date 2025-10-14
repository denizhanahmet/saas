# Routes package
from .auth import auth_bp
from .appointments import appointments_bp
from .dashboard import dashboard_bp
from .admin import admin_bp

__all__ = ['auth_bp', 'appointments_bp', 'dashboard_bp', 'admin_bp']
