"""
Notifications app configuration
"""
from django.apps import AppConfig

class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notifications'
    verbose_name = 'Notifications'
    
    def ready(self):
        """Import signal handlers when app is ready"""
        try:
            import apps.notifications.signals
        except ImportError:
            pass
