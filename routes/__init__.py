# Routes package
from .admin import admin_bp
from .appointments import appointments_bp
from .auth import auth_bp
from .dashboard import dashboard_bp

__all__ = ['auth_bp', 'appointments_bp', 'dashboard_bp', 'admin_bp']
