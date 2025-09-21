"""
Signal handlers for collaboration app
"""
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import (
    Collaboration, CollaborationParticipation, CollaborationMilestone,
    CollaborationMessage
)

@receiver(post_save, sender=CollaborationParticipation)
def update_collaboration_stats(sender, instance, **kwargs):
    """Update collaboration statistics"""
    collaboration = instance.collaboration
    collaboration.total_participants = collaboration.participations.filter(
        status__in=['approved', 'active', 'completed']
    ).count()
    collaboration.total_applications = collaboration.participations.count()
    collaboration.save(update_fields=['total_participants', 'total_applications'])

@receiver(post_save, sender=Collaboration)
def update_club_collaboration_count(sender, instance, created, **kwargs):
    """Update club's collaboration count"""
    if created:
        club = instance.initiator_club
        # Update club stats if the field exists
        try:
            if hasattr(club, 'total_collaborations'):
                club.total_collaborations = club.initiated_collaborations.filter(is_active=True).count()
                club.save(update_fields=['total_collaborations'])
        except Exception:
            pass

@receiver(post_save, sender=CollaborationParticipation)
def send_participation_notifications(sender, instance, created, **kwargs):
    """Send notifications for participation changes"""
    if created and instance.status == 'pending':
        # Notify collaboration owner about new application
        try:
            send_mail(
                subject=f'New collaboration application: {instance.collaboration.title}',
                message=f'''Hello {instance.collaboration.created_by.full_name},

{instance.club.name} has applied to join your collaboration "{instance.collaboration.title}".

Application details:
- Club: {instance.club.name}
- Primary Contact: {instance.primary_contact.full_name if instance.primary_contact else 'Not specified'}
- Committed Members: {instance.committed_members}
- Role: {instance.get_role_display()}

Please review this application in the collaboration management dashboard.

Best regards,
Campus Club Management Team''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.collaboration.created_by.email],
                fail_silently=True
            )
        except Exception as e:
            print(f"Failed to send participation notification: {e}")
    
    elif not created and instance.status == 'approved':
        # Notify club about approval
        try:
            send_mail(
                subject=f'Collaboration application approved: {instance.collaboration.title}',
                message=f'''Congratulations!

Your club {instance.club.name} has been approved to participate in "{instance.collaboration.title}".

Project details:
- Start Date: {instance.collaboration.start_date}
- End Date: {instance.collaboration.end_date}
- Your Role: {instance.get_role_display()}

You can now access the collaboration workspace and begin contributing.

Best regards,
{instance.collaboration.initiator_club.name} Team''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.primary_contact.email if instance.primary_contact else instance.club.email],
                fail_silently=True
            )
        except Exception as e:
            print(f"Failed to send approval notification: {e}")

@receiver(post_save, sender=CollaborationMilestone)
def update_collaboration_progress(sender, instance, **kwargs):
    """Update overall collaboration progress when milestone changes"""
    collaboration = instance.collaboration
    total_milestones = collaboration.milestone_objects.count()
    completed_milestones = collaboration.milestone_objects.filter(status='completed').count()
    
    if total_milestones > 0:
        progress = int((completed_milestones / total_milestones) * 100)
        collaboration.progress_percentage = progress
        collaboration.save(update_fields=['progress_percentage'])

@receiver(post_save, sender=CollaborationMilestone)
def send_milestone_notifications(sender, instance, created, **kwargs):
    """Send notifications for milestone updates"""
    if created:
        # Notify assigned clubs about new milestone
        try:
            for club in instance.assigned_clubs.all():
                club_contacts = club.memberships.filter(
                    status='active',
                    role__in=['admin', 'leader']
                ).select_related('user')
                
                for membership in club_contacts:
                    send_mail(
                        subject=f'New milestone assigned: {instance.title}',
                        message=f'''Hello {membership.user.full_name},

A new milestone has been assigned to {club.name} in the collaboration "{instance.collaboration.title}".

Milestone: {instance.title}
Due Date: {instance.due_date}
Description: {instance.description}

Please review the details and plan accordingly.

Best regards,
Collaboration Team''',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[membership.user.email],
                        fail_silently=True
                    )
        except Exception as e:
            print(f"Failed to send milestone assignment notification: {e}")
    
    elif not created and instance.status == 'completed':
        # Notify collaboration owner about milestone completion
        try:
            send_mail(
                subject=f'Milestone completed: {instance.title}',
                message=f'''Great news!

The milestone "{instance.title}" has been completed in your collaboration "{instance.collaboration.title}".

Completed by: {instance.completed_by.full_name if instance.completed_by else 'Unknown'}
Completed on: {instance.completed_at.strftime('%Y-%m-%d %H:%M') if instance.completed_at else 'Unknown'}

Overall project progress: {instance.collaboration.progress_percentage}%

Best regards,
Campus Club Management Team''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.collaboration.created_by.email],
                fail_silently=True
            )
        except Exception as e:
            print(f"Failed to send milestone completion notification: {e}")

@receiver(post_save, sender=CollaborationMessage)
def send_message_notifications(sender, instance, created, **kwargs):
    """Send notifications for important messages"""
    if created and instance.is_announcement:
        # Notify all participants about announcements
        try:
            participants = instance.collaboration.participations.filter(
                status__in=['approved', 'active']
            ).select_related('primary_contact', 'club')
            
            for participation in participants:
                contact = participation.primary_contact
                if contact:
                    send_mail(
                        subject=f'Collaboration Announcement: {instance.subject or instance.collaboration.title}',
                        message=f'''Hello {contact.full_name},

New announcement in "{instance.collaboration.title}":

{instance.subject}

{instance.content}

From: {instance.sender.full_name}

Best regards,
Collaboration Team''',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[contact.email],
                        fail_silently=True
                    )
        except Exception as e:
            print(f"Failed to send message notification: {e}")

@receiver(post_delete, sender=Collaboration)
def cleanup_collaboration_files(sender, instance, **kwargs):
    """Clean up collaboration files when deleted"""
    if instance.featured_image:
        try:
            instance.featured_image.delete(save=False)
        except Exception:
            pass

@receiver(post_delete, sender=CollaborationParticipation)
def update_collaboration_stats_on_delete(sender, instance, **kwargs):
    """Update collaboration statistics when participation is deleted"""
    try:
        collaboration = instance.collaboration
        collaboration.total_participants = collaboration.participations.filter(
            status__in=['approved', 'active', 'completed']
        ).count()
        collaboration.total_applications = collaboration.participations.count()
        collaboration.save(update_fields=['total_participants', 'total_applications'])
    except Exception:
        pass

@receiver(pre_save, sender=Collaboration)
def track_status_changes(sender, instance, **kwargs):
    """Track collaboration status changes for notifications"""
    if instance.pk:
        try:
            old_instance = Collaboration.objects.get(pk=instance.pk)
            
            # Notify when collaboration becomes active
            if (old_instance.status != 'in_progress' and 
                instance.status == 'in_progress'):
                
                # Send notification to all participants
                participants = instance.participations.filter(
                    status__in=['approved', 'active']
                ).select_related('primary_contact')
                
                for participation in participants:
                    if participation.primary_contact:
                        try:
                            send_mail(
                                subject=f'Collaboration Started: {instance.title}',
                                message=f'''Hello {participation.primary_contact.full_name},

The collaboration "{instance.title}" has officially started!

Project Duration: {instance.start_date} to {instance.end_date}
Your Club: {participation.club.name}
Your Role: {participation.get_role_display()}

Let's make this collaboration a success!

Best regards,
{instance.initiator_club.name} Team''',
                                from_email=settings.DEFAULT_FROM_EMAIL,
                                recipient_list=[participation.primary_contact.email],
                                fail_silently=True
                            )
                        except Exception as e:
                            print(f"Failed to send collaboration start notification: {e}")
                            
        except Collaboration.DoesNotExist:
            pass
