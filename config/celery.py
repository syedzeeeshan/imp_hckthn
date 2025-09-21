"""
Celery configuration for Campus Club Management Suite
Background task processing
"""
import os
from celery import Celery
from django.conf import settings

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('campus_club_suite')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery beat schedule for periodic tasks
app.conf.beat_schedule = {
    'send-event-reminders': {
        'task': 'apps.events.tasks.send_event_reminders',
        'schedule': 3600.0,  # Every hour
    },
    'generate-daily-analytics': {
        'task': 'apps.analytics.tasks.generate_daily_analytics',
        'schedule': 86400.0,  # Every day
    },
    'cleanup-expired-notifications': {
        'task': 'apps.notifications.tasks.cleanup_expired_notifications',
        'schedule': 43200.0,  # Every 12 hours
    },
}

app.conf.timezone = 'UTC'

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
