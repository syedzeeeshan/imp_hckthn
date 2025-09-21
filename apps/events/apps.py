"""
Events app configuration
"""
from django.apps import AppConfig

class EventsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.events'
    verbose_name = 'Events'
    
    def ready(self):
        """Import signal handlers when app is ready"""
        try:
            import apps.events.signals
        except ImportError:
            pass
