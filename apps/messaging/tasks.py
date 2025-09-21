"""
Celery tasks for messaging app
Background tasks for messaging system maintenance and notifications
"""
from celery import shared_task
from django.db import models
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
from .models import Conversation, Message, MessageReport

@shared_task
def cleanup_old_messages():
    """Clean up old messages (keep last 6 months)"""
    cutoff_date = timezone.now() - timedelta(days=180)
    
    # Delete very old messages
    old_messages = Message.objects.filter(
        created_at__lt=cutoff_date,
        is_deleted=True
    )
    
    deleted_count = old_messages.count()
    old_messages.delete()
    
    return f"Cleaned up {deleted_count} old messages"

@shared_task
def cleanup_empty_conversations():
    """Clean up conversations with no active participants"""
    empty_conversations = Conversation.objects.filter(
        conversation_participants__is_active=False
    ).annotate(
        active_participants=models.Count('conversation_participants', filter=models.Q(conversation_participants__is_active=True))
    ).filter(active_participants=0)
    
    cleaned_count = 0
    
    for conversation in empty_conversations:
        # Mark as inactive instead of deleting
        conversation.is_active = False
        conversation.save()
        cleaned_count += 1
    
    return f"Cleaned up {cleaned_count} empty conversations"

@shared_task
def process_message_reports():
    """Process pending message reports"""
    from apps.authentication.models import User
    
    # Get pending reports older than 24 hours
    day_ago = timezone.now() - timedelta(days=1)
    old_pending_reports = MessageReport.objects.filter(
        status='pending',
        created_at__lt=day_ago
    )
    
    # Auto-escalate to super admins
    super_admins = User.objects.filter(user_type='super_admin', is_active=True)
    
    escalated_count = 0
    
    for report in old_pending_reports:
        try:
            for admin in super_admins:
                send_mail(
                    subject=f'Urgent: Message Report Requires Review',
                    message=f'''A message report has been pending for over 24 hours.

Report ID: {report.id}
Reporter: {report.reporter.full_name}
Reason: {report.get_reason_display()}
Reported: {report.created_at}

Please review this report immediately.

Best regards,
Campus Club Management System''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[admin.email],
                    fail_silently=True
                )
            
            # Mark as escalated
            report.status = 'reviewed'
            report.save()
            escalated_count += 1
            
        except Exception as e:
            print(f"Failed to escalate report {report.id}: {e}")
            continue
    
    return f"Escalated {escalated_count} pending reports"

@shared_task
def update_conversation_stats():
    """Update conversation statistics"""
    from django.db.models import Count, Max
    
    conversations = Conversation.objects.filter(is_active=True)
    updated_count = 0
    
    for conversation in conversations:
        # Update message count
        actual_count = conversation.messages.filter(is_deleted=False).count()
        if conversation.message_count != actual_count:
            conversation.message_count = actual_count
            conversation.save(update_fields=['message_count'])
            updated_count += 1
    
    return f"Updated stats for {updated_count} conversations"

@shared_task
def send_unread_message_notifications():
    """Send notifications for unread messages (daily digest)"""
    from apps.authentication.models import User
    from django.db.models import Count
    
    # Get users with unread messages
    users_with_unread = User.objects.filter(
        is_active=True,
        conversation_participations__is_active=True,
        conversation_participations__conversation__messages__created_at__gt=models.F(
            'conversation_participations__last_read_at'
        )
    ).annotate(
        unread_count=Count('conversation_participations__conversation__messages')
    ).filter(unread_count__gt=0).distinct()
    
    notifications_sent = 0
    
    for user in users_with_unread:
        try:
            # Calculate total unread messages
            total_unread = 0
            conversations_with_unread = []
            
            for participation in user.conversation_participations.filter(is_active=True):
                conversation = participation.conversation
                unread_count = conversation.get_unread_count(user)
                
                if unread_count > 0:
                    total_unread += unread_count
                    conversations_with_unread.append({
                        'name': conversation.display_name,
                        'unread_count': unread_count
                    })
            
            if total_unread > 0:
                # Create conversation list for email
                conversation_list = "\n".join([
                    f"- {conv['name']}: {conv['unread_count']} unread"
                    for conv in conversations_with_unread[:5]  # Top 5
                ])
                
                if len(conversations_with_unread) > 5:
                    conversation_list += f"\n... and {len(conversations_with_unread) - 5} more"
                
                send_mail(
                    subject=f'You have {total_unread} unread messages',
                    message=f'''Hi {user.full_name},

You have {total_unread} unread messages in your conversations:

{conversation_list}

Visit the platform to catch up on your messages!

Best regards,
Campus Club Management Team''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True
                )
                
                notifications_sent += 1
                
        except Exception as e:
            print(f"Failed to send unread notification to {user.id}: {e}")
            continue
    
    return f"Sent unread notifications to {notifications_sent} users"

@shared_task
def archive_old_conversations():
    """Archive conversations inactive for 6+ months"""
    six_months_ago = timezone.now() - timedelta(days=180)
    
    inactive_conversations = Conversation.objects.filter(
        is_active=True,
        last_message_at__lt=six_months_ago
    )
    
    archived_count = 0
    
    for conversation in inactive_conversations:
        # Don't archive if it has recent participant activity
        recent_activity = conversation.conversation_participants.filter(
            last_seen_at__gte=six_months_ago
        ).exists()
        
        if not recent_activity:
            conversation.is_active = False
            conversation.save()
            archived_count += 1
    
    return f"Archived {archived_count} inactive conversations"

@shared_task
def cleanup_message_attachments():
    """Clean up orphaned message attachments"""
    from django.core.files.storage import default_storage
    import os
    
    # This is a simplified version - in production you'd want more sophisticated cleanup
    cleaned_count = 0
    
    # Find messages with attachments that are deleted
    deleted_messages_with_attachments = Message.objects.filter(
        is_deleted=True,
        attachment__isnull=False
    )
    
    for message in deleted_messages_with_attachments:
        try:
            if message.attachment and default_storage.exists(message.attachment.name):
                default_storage.delete(message.attachment.name)
                message.attachment = None
                message.save()
                cleaned_count += 1
        except Exception as e:
            print(f"Failed to clean attachment for message {message.id}: {e}")
            continue
    
    return f"Cleaned up {cleaned_count} orphaned attachments"
