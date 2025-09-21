"""
Signal handlers for events app
"""
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import models
from decimal import Decimal
from .models import Event, EventRegistration, EventFeedback

@receiver(post_save, sender=EventRegistration)
def update_event_registration_count(sender, instance, **kwargs):
    """Update event registration statistics"""
    event = instance.event
    event.total_registrations = event.registrations.filter(status__in=['registered', 'attended']).count()
    event.total_attendees = event.registrations.filter(status='attended').count()
    
    # Calculate revenue
    total_revenue = event.registrations.filter(
        status__in=['registered', 'attended'],
        payment_status='completed'
    ).aggregate(total=models.Sum('amount_paid'))['total'] or Decimal('0.00')
    event.total_revenue = total_revenue
    
    event.save(update_fields=['total_registrations', 'total_attendees', 'total_revenue'])

@receiver(post_delete, sender=EventRegistration)
def update_event_stats_on_delete(sender, instance, **kwargs):
    """Update event statistics when registration is deleted"""
    try:
        event = instance.event
        event.total_registrations = event.registrations.filter(status__in=['registered', 'attended']).count()
        event.total_attendees = event.registrations.filter(status='attended').count()
        
        from django.db.models import Sum
        total_revenue = event.registrations.filter(
            status__in=['registered', 'attended'],
            payment_status='completed'
        ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
        event.total_revenue = total_revenue
        
        event.save(update_fields=['total_registrations', 'total_attendees', 'total_revenue'])
    except Event.DoesNotExist:
        pass

@receiver(post_save, sender=Event)
def update_club_event_count(sender, instance, created, **kwargs):
    """Update club's event count"""
    if created:
        club = instance.club
        club.total_events = club.events.filter(is_active=True).count()
        club.save(update_fields=['total_events'])

@receiver(post_save, sender=EventRegistration)
def send_registration_notifications(sender, instance, created, **kwargs):
    """Send notifications for event registrations"""
    if created:
        try:
            if instance.status == 'registered':
                # Send confirmation to user
                send_mail(
                    subject=f'Registration confirmed for {instance.event.title}',
                    message=f'''Hello {instance.user.full_name},

Your registration for {instance.event.title} has been confirmed!

Event Details:
- Date: {instance.event.start_datetime.strftime('%B %d, %Y at %I:%M %p')}
- Location: {instance.event.location}
- Registration ID: {instance.id}

We look forward to seeing you at the event!

Best regards,
{instance.event.club.name} Team''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[instance.user.email],
                    fail_silently=True
                )
            
            elif instance.status == 'waitlisted':
                # Send waitlist notification
                send_mail(
                    subject=f'You\'re on the waitlist for {instance.event.title}',
                    message=f'''Hello {instance.user.full_name},

You have been added to the waitlist for {instance.event.title}.

We will notify you if a spot becomes available.

Event Details:
- Date: {instance.event.start_datetime.strftime('%B %d, %Y at %I:%M %p')}
- Location: {instance.event.location}

Thank you for your interest!

Best regards,
{instance.event.club.name} Team''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[instance.user.email],
                    fail_silently=True
                )
                
        except Exception as e:
            print(f"Failed to send registration notification: {e}")

@receiver(post_delete, sender=Event)
def cleanup_event_files(sender, instance, **kwargs):
    """Clean up event files when deleted"""
    if instance.featured_image:
        try:
            instance.featured_image.delete(save=False)
        except Exception:
            pass
    
    if instance.qr_code:
        try:
            instance.qr_code.delete(save=False)
        except Exception:
            pass

@receiver(pre_save, sender=Event)
def generate_qr_code_on_publish(sender, instance, **kwargs):
    """Generate QR code when event is published"""
    if instance.pk:
        try:
            old_instance = Event.objects.get(pk=instance.pk)
            # If status changed to published and no QR code exists
            if (old_instance.status != 'published' and 
                instance.status == 'published' and 
                not instance.qr_code):
                instance.generate_qr_code()
        except Event.DoesNotExist:
            pass

@receiver(post_save, sender=EventFeedback)
def update_user_profile_stats(sender, instance, created, **kwargs):
    """Update user profile stats when feedback is submitted"""
    if created and hasattr(instance.user, 'profile'):
        # Update user's event attendance count
        profile = instance.user.profile
        profile.total_events_attended = EventRegistration.objects.filter(
            user=instance.user,
            status='attended'
        ).count()
        profile.save(update_fields=['total_events_attended'])
