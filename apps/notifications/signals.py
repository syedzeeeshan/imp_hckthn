"""
Signal handlers for notifications app
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import NotificationSettings
from .utils import create_notification, get_notification_types

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_notification_settings(sender, instance, created, **kwargs):
    """Create notification settings for new users"""
    if created:
        NotificationSettings.objects.get_or_create(user=instance)

# Integration signals for creating notifications
@receiver(post_save, sender='clubs.ClubMembership')
def notify_club_membership(sender, instance, created, **kwargs):
    """Send notifications for club membership events"""
    from .utils import create_notification
    
    if created and instance.status == 'pending':
        # Notify club admins about new membership request
        try:
            notification_type = get_notification_types().filter(name='club_invitation').first()
            if notification_type:
                club_admins = instance.club.memberships.filter(
                    status='active',
                    role__in=['admin', 'leader']
                ).select_related('user')
                
                for admin_membership in club_admins:
                    create_notification(
                        recipient=admin_membership.user,
                        notification_type=notification_type,
                        title=f'New membership request for {instance.club.name}',
                        message=f'{instance.user.full_name} has requested to join {instance.club.name}',
                        related_object=instance,
                        action_url=f'/clubs/{instance.club.slug}/members/',
                        priority=2
                    )
        except Exception as e:
            print(f"Failed to send club membership notification: {e}")

@receiver(post_save, sender='events.EventRegistration')
def notify_event_registration(sender, instance, created, **kwargs):
    """Send notifications for event registrations"""
    if created and instance.status == 'registered':
        try:
            notification_type = get_notification_types().filter(name='event_registration').first()
            if notification_type:
                create_notification(
                    recipient=instance.user,
                    notification_type=notification_type,
                    title=f'Registration confirmed for {instance.event.title}',
                    message=f'You are now registered for {instance.event.title} on {instance.event.start_datetime.strftime("%B %d, %Y")}',
                    related_object=instance.event,
                    action_url=f'/events/{instance.event.slug}/',
                    priority=2
                )
        except Exception as e:
            print(f"Failed to send event registration notification: {e}")

@receiver(post_save, sender='gamification.UserBadge')
def notify_badge_earned(sender, instance, created, **kwargs):
    """Send notifications when badges are earned"""
    if created:
        try:
            notification_type = get_notification_types().filter(name='badge_earned').first()
            if notification_type:
                create_notification(
                    recipient=instance.user,
                    notification_type=notification_type,
                    title=f'Badge earned: {instance.badge.name}',
                    message=f'Congratulations! You\'ve earned the {instance.badge.name} badge',
                    related_object=instance.badge,
                    action_url='/gamification/badges/',
                    priority=2
                )
        except Exception as e:
            print(f"Failed to send badge earned notification: {e}")

@receiver(post_save, sender='messaging.Message')
def notify_new_message(sender, instance, created, **kwargs):
    """Send notifications for new messages"""
    if created and instance.message_type != 'system':
        try:
            notification_type = get_notification_types().filter(name='message_received').first()
            if notification_type:
                # Notify all conversation participants except sender
                participants = instance.conversation.conversation_participants.filter(
                    is_active=True
                ).exclude(user=instance.sender).select_related('user')
                
                for participant in participants:
                    create_notification(
                        recipient=participant.user,
                        notification_type=notification_type,
                        title=f'New message from {instance.sender.full_name}',
                        message=instance.content[:100] + "..." if len(instance.content) > 100 else instance.content,
                        sender=instance.sender,
                        related_object=instance.conversation,
                        action_url=f'/messages/{instance.conversation.id}/',
                        priority=2
                    )
        except Exception as e:
            print(f"Failed to send message notification: {e}")
