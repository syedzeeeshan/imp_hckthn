"""
Signal handlers for analytics app
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import AnalyticsReport, DashboardWidget

@receiver(post_save, sender=AnalyticsReport)
def schedule_next_report_generation(sender, instance, created, **kwargs):
    """Schedule next generation for recurring reports"""
    if created and instance.is_scheduled and instance.frequency != 'one_time':
        from datetime import timedelta
        
        now = timezone.now()
        
        if instance.frequency == 'daily':
            instance.next_generation_at = now + timedelta(days=1)
        elif instance.frequency == 'weekly':
            instance.next_generation_at = now + timedelta(weeks=1)
        elif instance.frequency == 'monthly':
            instance.next_generation_at = now + timedelta(days=30)
        elif instance.frequency == 'quarterly':
            instance.next_generation_at = now + timedelta(days=90)
        elif instance.frequency == 'yearly':
            instance.next_generation_at = now + timedelta(days=365)
        
        # Update without triggering signals again
        AnalyticsReport.objects.filter(id=instance.id).update(
            next_generation_at=instance.next_generation_at
        )

@receiver(post_save, sender=DashboardWidget)
def refresh_widget_on_config_change(sender, instance, created, **kwargs):
    """Refresh widget data when configuration changes"""
    if not created and instance.auto_refresh:
        try:
            instance.refresh_data()
        except Exception as e:
            print(f"Failed to refresh widget {instance.id} on config change: {str(e)}")
