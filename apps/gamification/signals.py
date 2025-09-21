"""
Signal handlers for gamification app
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from .models import UserBadge, PointsTransaction, UserAchievement
from .utils import check_user_badges, check_user_achievements

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_points_profile(sender, instance, created, **kwargs):
    """Create points profile for new users"""
    if created:
        from .models import UserPoints
        UserPoints.objects.get_or_create(user=instance)

@receiver(post_save, sender=UserBadge)
def update_badge_stats(sender, instance, created, **kwargs):
    """Update badge statistics when earned"""
    if created:
        badge = instance.badge
        badge.total_earned += 1
        badge.save(update_fields=['total_earned'])

@receiver(post_save, sender=PointsTransaction)
def check_achievements_on_transaction(sender, instance, created, **kwargs):
    """Check for achievements when points are awarded"""
    if created and instance.points > 0:
        # Check for badge achievements
        check_user_badges(instance.user)
        
        # Check for achievement progress updates
        check_user_achievements(instance.user, 'points_earned', {'points': instance.points})

@receiver(post_save, sender=UserAchievement)
def handle_achievement_completion(sender, instance, **kwargs):
    """Handle achievement completion"""
    if instance.status == 'completed' and not kwargs.get('created', False):
        # Send notification about achievement completion
        # This would integrate with the notifications app
        pass

# Integration signals from other apps
@receiver(post_save, sender='clubs.ClubMembership')
def award_points_for_club_activity(sender, instance, created, **kwargs):
    """Award points for club activities"""
    from .utils import award_points_for_activity
    
    if created and instance.status == 'active':
        award_points_for_activity(instance.user, 'club_join')
    elif instance.role in ['admin', 'leader'] and not created:
        award_points_for_activity(instance.user, 'club_leadership')

@receiver(post_save, sender='events.EventRegistration')
def award_points_for_event_activity(sender, instance, created, **kwargs):
    """Award points for event activities"""
    from .utils import award_points_for_activity
    
    if created and instance.status == 'registered':
        award_points_for_activity(instance.user, 'event_register')
    elif instance.status == 'attended' and not created:
        award_points_for_activity(instance.user, 'event_attend')

@receiver(post_save, sender='collaboration.CollaborationParticipation')
def award_points_for_collaboration_activity(sender, instance, created, **kwargs):
    """Award points for collaboration activities"""
    from .utils import award_points_for_activity
    
    if created and instance.status in ['approved', 'active']:
        award_points_for_activity(instance.user, 'collaboration_join')
    elif instance.status == 'completed' and not created:
        award_points_for_activity(instance.user, 'collaboration_complete')
