"""
Celery tasks for notifications app
Background tasks for notification processing and delivery
"""
from celery import shared_task
from django.utils import timezone
from django.db import models
from datetime import timedelta
from .models import Notification, NotificationBatch
from .utils import send_notification, cleanup_old_notifications

@shared_task
def process_scheduled_notifications():
    """Process scheduled notifications"""
    now = timezone.now()
    
    # Get notifications ready to be sent
    scheduled_notifications = Notification.objects.filter(
        status='pending',
        scheduled_at__lte=now
    )
    
    sent_count = 0
    failed_count = 0
    
    for notification in scheduled_notifications:
        if send_notification(notification):
            sent_count += 1
        else:
            failed_count += 1
    
    return f"Sent {sent_count} notifications, {failed_count} failed"

@shared_task
def retry_failed_notifications():
    """Retry failed notifications"""
    failed_notifications = Notification.objects.filter(
        status='failed',
        retry_count__lt=models.F('max_retries')
    )
    
    retried_count = 0
    
    for notification in failed_notifications:
        if notification.can_retry():
            notification.retry_count += 1
            notification.save()
            
            if send_notification(notification):
                retried_count += 1
    
    return f"Retried {retried_count} failed notifications"

@shared_task
def cleanup_old_notifications_task():
    """Clean up old notifications"""
    deleted_count = cleanup_old_notifications()
    return f"Cleaned up {deleted_count} old notifications"

@shared_task
def send_notification_batch(batch_id):
    """Send a notification batch"""
    try:
        batch = NotificationBatch.objects.get(id=batch_id)
        success = batch.send_batch()
        
        if success:
            return f"Successfully sent batch: {batch.name}"
        else:
            return f"Failed to send batch: {batch.name}"
            
    except NotificationBatch.DoesNotExist:
        return "Notification batch not found"

@shared_task
def process_email_digest():
    """Process email digest notifications"""
    from django.core.mail import send_mail
    from django.conf import settings
    from apps.authentication.models import User
    
    # Get users with email digest preferences
    users_with_digest = User.objects.filter(
        is_active=True,
        notification_settings__email_frequency='daily'
    )
    
    digest_sent = 0
    
    for user in users_with_digest:
        # Get unread notifications from last 24 hours
        yesterday = timezone.now() - timedelta(days=1)
        unread_notifications = Notification.objects.filter(
            recipient=user,
            status__in=['sent', 'delivered'],
            created_at__gte=yesterday
        )
        
        if unread_notifications.exists():
            # Create digest email content
            notifications_text = []
            for notification in unread_notifications[:10]:  # Limit to 10
                notifications_text.append(f"• {notification.title}")
            
            if unread_notifications.count() > 10:
                notifications_text.append(f"... and {unread_notifications.count() - 10} more")
            
            try:
                send_mail(
                    subject=f'Daily Digest - {unread_notifications.count()} notifications',
                    message=f'''Hi {user.full_name},

Here's your daily digest of notifications:

{chr(10).join(notifications_text)}

Visit the platform to view all your notifications.

Best regards,
Campus Club Management Team''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True
                )
                digest_sent += 1
            except Exception as e:
                print(f"Failed to send digest to {user.email}: {e}")
    
    return f"Sent daily digest to {digest_sent} users"

@shared_task
def update_notification_delivery_status():
    """Update notification delivery status"""
    # Mark old sent notifications as delivered
    one_hour_ago = timezone.now() - timedelta(hours=1)
    
    updated = Notification.objects.filter(
        status='sent',
        sent_at__lte=one_hour_ago
    ).update(
        status='delivered',
        delivered_at=timezone.now()
    )
    
    return f"Updated delivery status for {updated} notifications"
