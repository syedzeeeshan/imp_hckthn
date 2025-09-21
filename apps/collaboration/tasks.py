"""
Celery tasks for collaboration app
Background tasks for collaboration management and notifications
"""
from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
from .models import Collaboration, CollaborationMilestone, CollaborationParticipation

@shared_task
def send_collaboration_reminders():
    """Send reminders for upcoming collaboration deadlines"""
    now = timezone.now()
    
    # Application deadline reminders (3 days before)
    upcoming_deadlines = Collaboration.objects.filter(
        status='open',
        is_active=True,
        application_deadline__gte=now,
        application_deadline__lte=now + timedelta(days=3)
    ).select_related('created_by')
    
    reminder_count = 0
    
    for collaboration in upcoming_deadlines:
        try:
            send_mail(
                subject=f'Application Deadline Approaching: {collaboration.title}',
                message=f'''Hello {collaboration.created_by.full_name},

The application deadline for your collaboration "{collaboration.title}" is approaching.

Deadline: {collaboration.application_deadline.strftime('%Y-%m-%d %H:%M')}
Current Applications: {collaboration.total_applications}
Approved Participants: {collaboration.total_participants}

You may want to review and approve pending applications soon.

Best regards,
Campus Club Management Team''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[collaboration.created_by.email],
                fail_silently=True
            )
            reminder_count += 1
        except Exception as e:
            print(f"Failed to send deadline reminder for {collaboration.id}: {e}")
    
    return f"Sent {reminder_count} collaboration deadline reminders"

@shared_task
def send_milestone_reminders():
    """Send reminders for upcoming milestone deadlines"""
    now = timezone.now().date()
    
    # Milestone due date reminders (2 days before)
    upcoming_milestones = CollaborationMilestone.objects.filter(
        status__in=['pending', 'in_progress'],
        due_date__gte=now,
        due_date__lte=now + timedelta(days=2)
    ).select_related('collaboration', 'assigned_by').prefetch_related('assigned_clubs')
    
    reminder_count = 0
    
    for milestone in upcoming_milestones:
        try:
            # Notify assigned clubs
            for club in milestone.assigned_clubs.all():
                club_contacts = club.memberships.filter(
                    status='active',
                    role__in=['admin', 'leader']
                ).select_related('user')
                
                for membership in club_contacts:
                    send_mail(
                        subject=f'Milestone Due Soon: {milestone.title}',
                        message=f'''Hello {membership.user.full_name},

Reminder: The milestone "{milestone.title}" is due soon.

Collaboration: {milestone.collaboration.title}
Due Date: {milestone.due_date}
Current Progress: {milestone.progress_percentage}%

Please ensure the milestone is completed on time.

Best regards,
Collaboration Team''',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[membership.user.email],
                        fail_silently=True
                    )
                    reminder_count += 1
                    
        except Exception as e:
            print(f"Failed to send milestone reminder for {milestone.id}: {e}")
    
    return f"Sent {reminder_count} milestone reminders"

@shared_task
def update_overdue_milestones():
    """Update milestone status for overdue items"""
    now = timezone.now().date()
    
    overdue_milestones = CollaborationMilestone.objects.filter(
        status__in=['pending', 'in_progress'],
        due_date__lt=now
    )
    
    updated_count = overdue_milestones.update(status='overdue')
    
    return f"Marked {updated_count} milestones as overdue"

@shared_task
def close_expired_collaborations():
    """Close collaborations past their application deadline"""
    now = timezone.now()
    
    expired_collaborations = Collaboration.objects.filter(
        status='open',
        application_deadline__lt=now
    )
    
    closed_count = 0
    for collaboration in expired_collaborations:
        if collaboration.total_participants >= collaboration.min_participants:
            collaboration.status = 'in_progress'
            collaboration.save()
            closed_count += 1
        else:
            # Not enough participants, mark as cancelled
            collaboration.status = 'cancelled'
            collaboration.save()
    
    return f"Processed {closed_count} expired collaborations"

@shared_task
def calculate_collaboration_success_ratings():
    """Calculate success ratings for completed collaborations"""
    completed_collaborations = Collaboration.objects.filter(
        status='completed',
        success_rating=0  # Not yet calculated
    )
    
    updated_count = 0
    
    for collaboration in completed_collaborations:
        try:
            # Calculate based on various factors
            factors = []
            
            # Completion rate
            total_milestones = collaboration.milestone_objects.count()
            completed_milestones = collaboration.milestone_objects.filter(status='completed').count()
            if total_milestones > 0:
                completion_rate = completed_milestones / total_milestones
                factors.append(completion_rate)
            
            # Participant retention
            if collaboration.total_participants > 0:
                active_participants = collaboration.participations.filter(
                    status__in=['active', 'completed']
                ).count()
                retention_rate = active_participants / collaboration.total_participants
                factors.append(retention_rate)
            
            # Time management (completed on time)
            if collaboration.end_date >= timezone.now().date():
                factors.append(1.0)  # On time
            else:
                factors.append(0.8)  # Late completion
            
            # Calculate average success rating
            if factors:
                success_rating = sum(factors) / len(factors) * 5  # Scale to 5
                collaboration.success_rating = round(success_rating, 2)
                collaboration.save()
                updated_count += 1
                
        except Exception as e:
            print(f"Failed to calculate success rating for {collaboration.id}: {e}")
    
    return f"Updated success ratings for {updated_count} collaborations"

@shared_task
def send_collaboration_completion_surveys():
    """Send completion surveys to collaboration participants"""
    recently_completed = Collaboration.objects.filter(
        status='completed',
        end_date__gte=timezone.now().date() - timedelta(days=7),
        end_date__lte=timezone.now().date()
    )
    
    survey_count = 0
    
    for collaboration in recently_completed:
        try:
            participants = collaboration.participations.filter(
                status__in=['active', 'completed']
            ).select_related('primary_contact', 'club')
            
            for participation in participants:
                if participation.primary_contact:
                    send_mail(
                        subject=f'Collaboration Completed: Share Your Experience - {collaboration.title}',
                        message=f'''Hello {participation.primary_contact.full_name},

Congratulations on completing the collaboration "{collaboration.title}"!

We would love to hear about your experience to help improve future collaborations.

Collaboration Details:
- Duration: {collaboration.start_date} to {collaboration.end_date}
- Your Club: {participation.club.name}
- Your Role: {participation.get_role_display()}

Please take a moment to provide feedback on your collaboration experience.

Thank you for your participation!

Best regards,
Campus Club Management Team''',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[participation.primary_contact.email],
                        fail_silently=True
                    )
                    survey_count += 1
                    
        except Exception as e:
            print(f"Failed to send completion survey for {collaboration.id}: {e}")
    
    return f"Sent {survey_count} collaboration completion surveys"

@shared_task
def cleanup_old_collaborations():
    """Archive old completed collaborations"""
    cutoff_date = timezone.now().date() - timedelta(days=365)  # 1 year old
    
    old_collaborations = Collaboration.objects.filter(
        status='completed',
        end_date__lt=cutoff_date,
        is_active=True
    )
    
    archived_count = old_collaborations.update(is_active=False)
    
    return f"Archived {archived_count} old collaborations"
