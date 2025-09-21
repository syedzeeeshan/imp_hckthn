"""
Messaging app configuration
"""
from django.apps import AppConfig

class MessagingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.messaging'
    verbose_name = 'Messaging'
    
    def ready(self):
        """Import signal handlers when app is ready"""
        try:
            import apps.messaging.signals
        except ImportError:
            pass
