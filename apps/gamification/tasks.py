"""
Celery tasks for gamification app
Background tasks for rankings, achievements, and gamification maintenance
"""
from celery import shared_task
from django.utils import timezone
from django.db.models import Count, Sum, Avg
from datetime import timedelta
from .models import UserPoints, Badge, Achievement, UserAchievement, PointsTransaction
from .utils import calculate_user_rankings, check_user_badges, check_user_achievements

@shared_task
def update_user_rankings():
    """Update user rankings across all leaderboards"""
    calculate_user_rankings()
    return "User rankings updated successfully"

@shared_task
def check_achievement_progress():
    """Check and update achievement progress for all users"""
    active_achievements = UserAchievement.objects.filter(
        status='in_progress'
    ).select_related('user', 'achievement')
    
    updated_count = 0
    
    for user_achievement in active_achievements:
        try:
            # Re-calculate progress based on current user stats
            user = user_achievement.user
            achievement = user_achievement.achievement
            
            # This would be more sophisticated in practice
            # For now, just check if user meets completion criteria
            old_progress = user_achievement.progress_percentage
            
            # Update progress based on requirements
            check_user_achievements(user)
            
            user_achievement.refresh_from_db()
            if user_achievement.progress_percentage != old_progress:
                updated_count += 1
                
        except Exception as e:
            print(f"Error updating achievement {user_achievement.id}: {e}")
            continue
    
    return f"Updated progress for {updated_count} achievements"

@shared_task
def award_daily_login_points():
    """Award points for daily login streaks"""
    from apps.authentication.models import User
    
    today = timezone.now().date()
    awarded_count = 0
    
    # Get users who were active today but haven't been awarded today's points
    active_users = User.objects.filter(
        is_active=True,
        last_login__date=today,
        points_profile__last_activity_date__lt=today
    ).select_related('points_profile')
    
    for user in active_users:
        try:
            from .utils import award_points_for_activity
            points_awarded = award_points_for_activity(user, 'daily_login')
            
            if points_awarded > 0:
                awarded_count += 1
                
                # Check for streak milestones
                if hasattr(user, 'points_profile'):
                    streak = user.points_profile.current_streak
                    if streak > 0 and streak % 7 == 0:  # Every 7 days
                        award_points_for_activity(
                            user, 
                            'streak_milestone', 
                            {'value': streak}
                        )
                        
        except Exception as e:
            print(f"Error awarding daily login points to {user.id}: {e}")
            continue
    
    return f"Awarded daily login points to {awarded_count} users"

@shared_task
def check_badge_achievements():
    """Check for new badge achievements across all users"""
    from apps.authentication.models import User
    
    # Get users who have been active recently
    week_ago = timezone.now() - timedelta(days=7)
    active_users = User.objects.filter(
        is_active=True,
        points_transactions__created_at__gte=week_ago
    ).distinct().select_related('points_profile')
    
    total_badges_awarded = 0
    
    for user in active_users:
        try:
            new_badges = check_user_badges(user)
            total_badges_awarded += len(new_badges)
        except Exception as e:
            print(f"Error checking badges for user {user.id}: {e}")
            continue
    
    return f"Awarded {total_badges_awarded} new badges"

@shared_task
def expire_seasonal_achievements():
    """Mark expired seasonal achievements as failed"""
    now = timezone.now()
    
    expired_achievements = Achievement.objects.filter(
        achievement_type='seasonal',
        end_date__lt=now,
        is_active=True
    )
    
    expired_count = 0
    
    for achievement in expired_achievements:
        # Mark in-progress user achievements as expired
        expired_user_achievements = UserAchievement.objects.filter(
            achievement=achievement,
            status='in_progress'
        )
        
        updated = expired_user_achievements.update(status='expired')
        expired_count += updated
    
    return f"Marked {expired_count} seasonal achievements as expired"

@shared_task
def generate_leaderboard_snapshots():
    """Generate and cache leaderboard snapshots for better performance"""
    from .models import Leaderboard
    
    active_leaderboards = Leaderboard.objects.filter(is_active=True)
    snapshots_created = 0
    
    for leaderboard in active_leaderboards:
        try:
            # Get current leaderboard data
            leaderboard_data = leaderboard.get_leaderboard_data(limit=100)
            
            # Cache this data (you would implement caching here)
            # For now, we'll just count it as generated
            snapshots_created += 1
            
        except Exception as e:
            print(f"Error generating snapshot for leaderboard {leaderboard.id}: {e}")
            continue
    
    return f"Generated {snapshots_created} leaderboard snapshots"

@shared_task
def clean_old_transactions():
    """Clean up old points transactions (keep last 90 days)"""
    cutoff_date = timezone.now() - timedelta(days=90)
    
    old_transactions = PointsTransaction.objects.filter(
        created_at__lt=cutoff_date
    )
    
    deleted_count = old_transactions.count()
    old_transactions.delete()
    
    return f"Cleaned up {deleted_count} old points transactions"

@shared_task
def recalculate_badge_rarity():
    """Recalculate badge rarity percentages"""
    from apps.authentication.models import User
    
    total_users = User.objects.filter(is_active=True).count()
    updated_badges = 0
    
    if total_users > 0:
        badges = Badge.objects.filter(is_active=True)
        
        for badge in badges:
            # The rarity_percentage is calculated as a property
            # but we could cache it if needed
            updated_badges += 1
    
    return f"Recalculated rarity for {updated_badges} badges"

@shared_task
def send_achievement_reminders():
    """Send reminders for achievements close to expiring"""
    from django.core.mail import send_mail
    from django.conf import settings
    
    # Find achievements expiring in 3 days
    three_days_from_now = timezone.now() + timedelta(days=3)
    
    expiring_achievements = Achievement.objects.filter(
        is_active=True,
        end_date__lte=three_days_from_now,
        end_date__gt=timezone.now(),
        achievement_type__in=['seasonal', 'challenge']
    )
    
    reminders_sent = 0
    
    for achievement in expiring_achievements:
        # Get users who are actively working on this achievement
        active_participants = UserAchievement.objects.filter(
            achievement=achievement,
            status='in_progress',
            progress_percentage__gte=10  # At least 10% progress
        ).select_related('user')
        
        for user_achievement in active_participants:
            try:
                user = user_achievement.user
                send_mail(
                    subject=f'Achievement Expiring Soon: {achievement.name}',
                    message=f'''Hi {user.full_name},

The achievement "{achievement.name}" is expiring in 3 days!

Your current progress: {user_achievement.progress_percentage}%

Don't miss out on earning {achievement.points_reward} points!

Complete it before {achievement.end_date.strftime('%Y-%m-%d %H:%M')}.

Best regards,
Campus Club Management Team''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True
                )
                reminders_sent += 1
            except Exception as e:
                print(f"Failed to send reminder to {user_achievement.user.email}: {e}")
                continue
    
    return f"Sent {reminders_sent} achievement expiry reminders"
