"""
Gamification app configuration
"""
from django.apps import AppConfig

class GamificationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.gamification'
    verbose_name = 'Gamification'
    
    def ready(self):
        """Import signal handlers when app is ready"""
        try:
            import apps.gamification.signals
        except ImportError:
            pass
