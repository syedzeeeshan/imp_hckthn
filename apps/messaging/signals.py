"""
Signal handlers for messaging app
"""
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import Conversation, ConversationParticipant, Message, MessageReport

@receiver(post_save, sender=Message)
def update_conversation_on_message(sender, instance, created, **kwargs):
    """Update conversation stats when message is created"""
    if created and not instance.is_deleted:
        conversation = instance.conversation
        conversation.last_message_at = instance.created_at
        conversation.save(update_fields=['last_message_at'])

@receiver(post_save, sender=ConversationParticipant)
def create_system_message_on_join(sender, instance, created, **kwargs):
    """Create system message when user joins conversation"""
    if created and instance.conversation.conversation_type in ['group', 'club']:
        Message.objects.create(
            conversation=instance.conversation,
            sender=instance.user,
            message_type='system',
            content=f"{instance.user.full_name} joined the conversation"
        )

@receiver(post_save, sender=ConversationParticipant)
def create_system_message_on_leave(sender, instance, **kwargs):
    """Create system message when user leaves conversation"""
    if instance.left_at and not instance.is_active and not kwargs.get('created', False):
        Message.objects.create(
            conversation=instance.conversation,
            sender=instance.user,
            message_type='system',
            content=f"{instance.user.full_name} left the conversation"
        )

@receiver(post_save, sender=MessageReport)
def send_report_notification(sender, instance, created, **kwargs):
    """Send notification about message reports to admins"""
    if created:
        try:
            # Get super admins and college admins
            from apps.authentication.models import User
            admins = User.objects.filter(
                is_active=True,
                user_type__in=['super_admin', 'college_admin']
            )
            
            for admin in admins:
                send_mail(
                    subject='New Message Report',
                    message=f'''A new message has been reported.

Reporter: {instance.reporter.full_name}
Reason: {instance.get_reason_display()}
Description: {instance.description}

Please review this report in the admin panel.

Best regards,
Campus Club Management System''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[admin.email],
                    fail_silently=True
                )
        except Exception as e:
            print(f"Failed to send report notification: {e}")

@receiver(pre_save, sender=Message)
def handle_message_edit(sender, instance, **kwargs):
    """Handle message editing"""
    if instance.pk:
        try:
            old_message = Message.objects.get(pk=instance.pk)
            if old_message.content != instance.content:
                instance.is_edited = True
        except Message.DoesNotExist:
            pass

@receiver(post_delete, sender=Message)
def cleanup_message_files(sender, instance, **kwargs):
    """Clean up message attachment files when message is deleted"""
    if instance.attachment:
        try:
            instance.attachment.delete(save=False)
        except Exception:
            pass
