"""
Signal handlers for authentication app
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import User, UserProfile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create UserProfile when User is created"""
    if created:
        UserProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save UserProfile when User is saved"""
    if hasattr(instance, 'profile'):
        instance.profile.save()

@receiver(post_save, sender=User)
def send_welcome_notification(sender, instance, created, **kwargs):
    """Send welcome notification to new users"""
    if created and instance.is_verified:
        try:
            subject = f'Welcome to Campus Club Management Suite, {instance.full_name}!'
            message = f"""
            Welcome to Campus Club Management Suite!
            
            Your account has been successfully created and verified.
            
            College: {instance.college_name}
            User Type: {instance.get_user_type_display()}
            
            You can now start exploring clubs, attending events, and collaborating with other students.
            
            Best regards,
            Campus Club Management Team
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.email],
                fail_silently=True
            )
        except Exception as e:
            print(f"Failed to send welcome email to {instance.email}: {e}")

@receiver(post_delete, sender=User)
def cleanup_user_data(sender, instance, **kwargs):
    """Cleanup related data when user is deleted"""
    # Delete user's avatar file if it exists
    if instance.avatar:
        try:
            instance.avatar.delete(save=False)
        except Exception:
            pass
