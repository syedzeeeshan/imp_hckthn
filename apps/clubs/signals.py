"""
Signal handlers for clubs app
"""
from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import Club, ClubMembership, ClubAnnouncement

@receiver(post_save, sender=Club)
def create_club_settings(sender, instance, created, **kwargs):
    """Create club settings when club is created"""
    if created:
        from .models import ClubSettings
        ClubSettings.objects.get_or_create(club=instance)

@receiver(post_save, sender=ClubMembership)
def update_club_stats(sender, instance, created, **kwargs):
    """Update club statistics when membership changes"""
    if instance.status == 'active':
        # Update user profile stats
        if hasattr(instance.user, 'profile'):
            profile = instance.user.profile
            profile.total_clubs_joined = ClubMembership.objects.filter(
                user=instance.user, 
                status='active'
            ).count()
            profile.save(update_fields=['total_clubs_joined'])

@receiver(post_save, sender=ClubMembership)
def send_membership_notifications(sender, instance, created, **kwargs):
    """Send notifications for membership changes"""
    if created and instance.status == 'pending':
        # Notify club leaders about new membership request
        try:
            club_leaders = instance.club.memberships.filter(
                status='active',
                role__in=['admin', 'leader']
            ).select_related('user')
            
            for leadership in club_leaders:
                send_mail(
                    subject=f'New membership request for {instance.club.name}',
                    message=f'''Hello {leadership.user.full_name},

{instance.user.full_name} has requested to join {instance.club.name}.

Please review and approve/reject this request in the club management dashboard.

Best regards,
Campus Club Management Team''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[leadership.user.email],
                    fail_silently=True
                )
        except Exception as e:
            print(f"Failed to send membership notification: {e}")
    
    elif instance.status == 'active' and not created:
        # Notify user about membership approval
        try:
            send_mail(
                subject=f'Welcome to {instance.club.name}!',
                message=f'''Congratulations {instance.user.full_name}!

Your membership request for {instance.club.name} has been approved.

You can now participate in club activities and events.

Best regards,
{instance.club.name} Team''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.user.email],
                fail_silently=True
            )
        except Exception as e:
            print(f"Failed to send approval notification: {e}")

@receiver(post_delete, sender=Club)
def cleanup_club_files(sender, instance, **kwargs):
    """Clean up club files when club is deleted"""
    if instance.logo:
        try:
            instance.logo.delete(save=False)
        except Exception:
            pass
    
    if instance.cover_image:
        try:
            instance.cover_image.delete(save=False)
        except Exception:
            pass

@receiver(post_save, sender=ClubAnnouncement)
def send_announcement_notifications(sender, instance, created, **kwargs):
    """Send notifications for new announcements"""
    if created and instance.is_published and instance.send_notification:
        try:
            # Get target members
            if instance.target_all_members:
                members = instance.club.memberships.filter(status='active')
            else:
                members = instance.club.memberships.filter(
                    status='active',
                    role__in=instance.target_roles
                )
            
            # Send notifications
            for membership in members.select_related('user'):
                if instance.send_email:
                    send_mail(
                        subject=f'New announcement from {instance.club.name}',
                        message=f'''Hello {membership.user.full_name},

New announcement from {instance.club.name}:

{instance.title}

{instance.content}

Best regards,
{instance.club.name} Team''',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[membership.user.email],
                        fail_silently=True
                    )
        except Exception as e:
            print(f"Failed to send announcement notifications: {e}")
