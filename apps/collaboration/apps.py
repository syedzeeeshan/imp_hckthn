"""
Collaboration app configuration
"""
from django.apps import AppConfig

class CollaborationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.collaboration'
    verbose_name = 'Collaboration'
    
    def ready(self):
        """Import signal handlers when app is ready"""
        try:
            import apps.collaboration.signals
        except ImportError:
            pass
