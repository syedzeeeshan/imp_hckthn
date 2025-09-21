"""
Celery tasks for events app
Background tasks for event management and notifications
"""
from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from datetime import timedelta
from .models import Event, EventRegistration


@shared_task
def send_event_reminders():
    """Send event reminders to registered users"""
    now = timezone.now()
    
    # Events starting in 24 hours
    events_24h = Event.objects.filter(
        is_active=True,
        status='published',
        start_datetime__gte=now,
        start_datetime__lte=now + timedelta(hours=24)
    ).prefetch_related('registrations__user')
    
    # Events starting in 1 hour
    events_1h = Event.objects.filter(
        is_active=True,
        status='published',
        start_datetime__gte=now,
        start_datetime__lte=now + timedelta(hours=1)
    ).prefetch_related('registrations__user')
    
    reminder_count = 0
    
    for event in events_24h:
        registrations = event.registrations.filter(status='registered')
        for registration in registrations:
            try:
                send_mail(
                    subject=f'Event Reminder: {event.title} - Tomorrow',
                    message=f'Hi {registration.user.full_name},\n\n'
                           f'This is a reminder that you are registered for:\n\n'
                           f'{event.title}\n'
                           f'Date: {event.start_datetime.strftime("%B %d, %Y at %I:%M %p")}\n'
                           f'Location: {event.location}\n\n'
                           f'We look forward to seeing you there!\n\n'
                           f'Best regards,\n{event.club.name}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[registration.user.email],
                    fail_silently=True
                )
                reminder_count += 1
            except Exception as e:
                print(f"Failed to send 24h reminder to {registration.user.email}: {e}")
    
    for event in events_1h:
        registrations = event.registrations.filter(status='registered')
        for registration in registrations:
            try:
                send_mail(
                    subject=f'Event Starting Soon: {event.title}',
                    message=f'Hi {registration.user.full_name},\n\n'
                           f'{event.title} is starting in 1 hour!\n\n'
                           f'Time: {event.start_datetime.strftime("%I:%M %p")}\n'
                           f'Location: {event.location}\n'
                           f'{f"Meeting Link: {event.meeting_link}" if event.is_online and event.meeting_link else ""}\n\n'
                           f'See you soon!\n\n'
                           f'Best regards,\n{event.club.name}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[registration.user.email],
                    fail_silently=True
                )
                reminder_count += 1
            except Exception as e:
                print(f"Failed to send 1h reminder to {registration.user.email}: {e}")
    
    return f"Sent {reminder_count} event reminders"


@shared_task
def update_event_status():
    """Update event statuses based on current time"""
    now = timezone.now()
    
    # Mark events as ongoing
    ongoing_count = Event.objects.filter(
        status='published',
        start_datetime__lte=now,
        end_datetime__gt=now
    ).update(status='ongoing')
    
    # Mark events as completed
    completed_count = Event.objects.filter(
        status__in=['published', 'ongoing'],
        end_datetime__lte=now
    ).update(status='completed')
    
    return f"Updated {ongoing_count} events to ongoing, {completed_count} events to completed"


@shared_task
def send_event_feedback_requests():
    """Send feedback requests for completed events"""
    cutoff_time = timezone.now() - timedelta(hours=2)  # 2 hours after event ends
    
    completed_events = Event.objects.filter(
        status='completed',
        end_datetime__lte=cutoff_time,
        end_datetime__gte=timezone.now() - timedelta(days=7)  # Within last 7 days
    )
    
    feedback_count = 0
    
    for event in completed_events:
        # Get attendees who haven't submitted feedback
        attendees = event.registrations.filter(
            status='attended'
        ).exclude(
            user__in=event.feedback_entries.values_list('user', flat=True)
        ).select_related('user')
        
        for registration in attendees:
            try:
                send_mail(
                    subject=f'How was {event.title}? Share your feedback',
                    message=f'Hi {registration.user.full_name},\n\n'
                           f'Thank you for attending {event.title}!\n\n'
                           f'We would love to hear your feedback to help us improve future events.\n\n'
                           f'Please take a moment to rate and review the event.\n\n'
                           f'Thank you!\n\n'
                           f'Best regards,\n{event.club.name}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[registration.user.email],
                    fail_silently=True
                )
                feedback_count += 1
            except Exception as e:
                print(f"Failed to send feedback request to {registration.user.email}: {e}")
    
    return f"Sent {feedback_count} feedback requests"


@shared_task
def cleanup_old_events():
    """Archive or clean up old events"""
    # Archive events older than 1 year
    one_year_ago = timezone.now() - timedelta(days=365)
    
    archived_count = Event.objects.filter(
        end_datetime__lt=one_year_ago,
        is_active=True
    ).update(is_active=False)
    
    return f"Archived {archived_count} old events"


@shared_task
def generate_event_certificates(event_id):
    """Generate certificates for event attendees"""
    try:
        event = Event.objects.get(id=event_id, status='completed')
        attendees = event.registrations.filter(status='attended')
        
        certificate_count = 0
        
        for registration in attendees:
            # This would integrate with a certificate generation service
            # For now, just log the action
            print(f"Generating certificate for {registration.user.full_name} - Event: {event.title}")
            certificate_count += 1
        
        return f"Generated {certificate_count} certificates for {event.title}"
        
    except Event.DoesNotExist:
        return "Event not found or not completed"
    except Exception as e:
        return f"Error generating certificates: {str(e)}"
