"""
Notification utilities for Campus Club Management Suite
Helper functions for creating and sending notifications
"""
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Notification, NotificationSettings, NotificationType

def create_notification(recipient, notification_type, title, message, 
                       sender=None, action_url='', related_object=None,
                       data=None, priority=2, send_email=None, send_push=None, 
                       send_in_app=None, scheduled_at=None, expires_at=None):
    """Create and queue a notification"""
    
    if data is None:
        data = {}
    
    # Get user's notification settings
    settings_obj, created = NotificationSettings.objects.get_or_create(user=recipient)
    
    # Check if notifications are enabled for this user and type
    if not settings_obj.notifications_enabled:
        return None
    
    if not settings_obj.is_type_enabled(notification_type, 'in_app'):
        return None
    
    # Set delivery channels based on user preferences
    if send_email is None:
        send_email = settings_obj.is_type_enabled(notification_type, 'email')
    if send_push is None:
        send_push = settings_obj.is_type_enabled(notification_type, 'push')
    if send_in_app is None:
        send_in_app = settings_obj.is_type_enabled(notification_type, 'in_app')
    
    # Set related object fields
    related_object_type = None
    related_object_id = None
    if related_object:
        related_object_type = f"{related_object._meta.app_label}.{related_object._meta.model_name}"
        related_object_id = related_object.id
    
    # Create notification
    notification = Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        sender=sender,
        title=title,
        message=message,
        action_url=action_url,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        data=data,
        priority=priority,
        send_email=send_email,
        send_push=send_push,
        send_in_app=send_in_app,
        scheduled_at=scheduled_at or timezone.now(),
        expires_at=expires_at
    )
    
    # Send immediately if not scheduled
    if not scheduled_at or scheduled_at <= timezone.now():
        send_notification(notification)
    
    return notification

def send_notification(notification):
    """Send a notification through configured channels"""
    try:
        # Check if in quiet hours
        if notification.recipient.notification_settings.is_in_quiet_hours():
            # Delay sending until quiet hours end
            return False
        
        # Send email
        if notification.send_email and not notification.email_sent:
            success = send_email_notification(notification)
            notification.email_sent = success
        
        # Send push notification
        if notification.send_push and not notification.push_sent:
            success = send_push_notification(notification)
            notification.push_sent = success
        
        # In-app notification is always "sent" since it's stored in database
        notification.in_app_sent = True
        
        # Update status
        notification.status = 'sent'
        notification.sent_at = timezone.now()
        notification.save()
        
        return True
        
    except Exception as e:
        notification.error_message = str(e)
        notification.status = 'failed'
        notification.save()
        return False

def send_email_notification(notification):
    """Send email notification"""
    try:
        send_mail(
            subject=notification.title,
            message=f'''{notification.message}

{f"From: {notification.sender.full_name}" if notification.sender else ""}

{f"Click here to view: {notification.action_url}" if notification.action_url else ""}

---
This is an automated message from Campus Club Management System.
To update your notification preferences, visit your account settings.''',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[notification.recipient.email],
            fail_silently=False
        )
        return True
    except Exception as e:
        print(f"Failed to send email notification: {e}")
        return False

def send_push_notification(notification):
    """Send push notification"""
    try:
        # Get user's active push devices
        devices = notification.recipient.push_devices.filter(is_active=True)
        
        if not devices.exists():
            return False
        
        # This is where you would integrate with Firebase, OneSignal, or other push services
        # For now, we'll just mark as sent
        
        for device in devices:
            # Send to device based on type
            if device.device_type == 'ios':
                success = send_ios_push(device, notification)
            elif device.device_type == 'android':
                success = send_android_push(device, notification)
            elif device.device_type == 'web':
                success = send_web_push(device, notification)
            
            if success:
                device.last_used_at = timezone.now()
                device.save()
        
        return True
        
    except Exception as e:
        print(f"Failed to send push notification: {e}")
        return False

def send_ios_push(device, notification):
    """Send iOS push notification"""
    # Implement iOS push notification logic here
    # Using APNs (Apple Push Notification service)
    return True

def send_android_push(device, notification):
    """Send Android push notification"""
    # Implement Android push notification logic here
    # Using FCM (Firebase Cloud Messaging)
    return True

def send_web_push(device, notification):
    """Send web push notification"""
    # Implement web push notification logic here
    # Using Web Push Protocol
    return True

def create_bulk_notifications(recipients, notification_type, title, message, 
                             sender=None, **kwargs):
    """Create notifications for multiple recipients"""
    notifications = []
    
    for recipient in recipients:
        notification = create_notification(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            sender=sender,
            **kwargs
        )
        if notification:
            notifications.append(notification)
    
    return notifications

def get_notification_types():
    """Get all active notification types"""
    return NotificationType.objects.filter(is_active=True).order_by('priority', 'name')

def create_default_notification_types():
    """Create default notification types"""
    default_types = [
        {
            'name': 'club_invitation',
            'description': 'Invitation to join a club',
            'icon': '🎯',
            'color': '#007bff',
            'priority': 1
        },
        {
            'name': 'event_reminder',
            'description': 'Reminder for upcoming events',
            'icon': '📅',
            'color': '#28a745',
            'priority': 1
        },
        {
            'name': 'event_registration',
            'description': 'Event registration confirmation',
            'icon': '✅',
            'color': '#17a2b8',
            'priority': 2
        },
        {
            'name': 'club_announcement',
            'description': 'Club announcements',
            'icon': '📢',
            'color': '#ffc107',
            'priority': 2
        },
        {
            'name': 'collaboration_invite',
            'description': 'Collaboration invitation',
            'icon': '🤝',
            'color': '#6f42c1',
            'priority': 1
        },
        {
            'name': 'message_received',
            'description': 'New message received',
            'icon': '💬',
            'color': '#fd7e14',
            'priority': 2
        },
        {
            'name': 'badge_earned',
            'description': 'New badge earned',
            'icon': '🏆',
            'color': '#e83e8c',
            'priority': 2
        },
        {
            'name': 'achievement_unlocked',
            'description': 'Achievement unlocked',
            'icon': '🎉',
            'color': '#20c997',
            'priority': 2
        },
        {
            'name': 'system_update',
            'description': 'System updates and maintenance',
            'icon': '⚙️',
            'color': '#6c757d',
            'priority': 3
        }
    ]
    
    created_count = 0
    
    for type_data in default_types:
        notification_type, created = NotificationType.objects.get_or_create(
            name=type_data['name'],
            defaults=type_data
        )
        if created:
            created_count += 1
            print(f"Created notification type: {notification_type.name}")
    
    return created_count

def cleanup_old_notifications():
    """Clean up old read notifications"""
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=30)  # Keep for 30 days
    
    old_notifications = Notification.objects.filter(
        status='read',
        read_at__lt=cutoff_date
    )
    
    deleted_count = old_notifications.count()
    old_notifications.delete()
    
    return deleted_count

def get_user_notification_summary(user):
    """Get notification summary for a user"""
    total = Notification.objects.filter(recipient=user, in_app_sent=True).count()
    unread = Notification.objects.filter(recipient=user, in_app_sent=True).exclude(status='read').count()
    high_priority = Notification.objects.filter(
        recipient=user, 
        in_app_sent=True, 
        priority=1
    ).exclude(status='read').count()
    
    return {
        'total_notifications': total,
        'unread_count': unread,
        'high_priority_count': high_priority,
        'read_percentage': round((total - unread) / total * 100, 1) if total > 0 else 0
    }
