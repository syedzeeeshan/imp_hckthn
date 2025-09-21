"""
Gamification utilities for Campus Club Management Suite
Helper functions for points, badges, and achievements
"""
from django.utils import timezone
from .models import Badge, UserBadge, UserPoints, PointsTransaction, Achievement, UserAchievement

def award_points_for_activity(user, activity_type, activity_data=None):
    """Award points based on activity type"""
    if activity_data is None:
        activity_data = {}
    
    points_map = {
        # Club activities
        'club_join': 50,
        'club_create': 100,
        'club_leadership': 200,
        
        # Event activities
        'event_register': 10,
        'event_attend': 25,
        'event_create': 75,
        'event_organize': 150,
        
        # Social activities
        'collaboration_join': 100,
        'collaboration_create': 200,
        'collaboration_complete': 300,
        
        # Academic activities
        'achievement_complete': 500,
        'milestone_complete': 100,
        
        # Engagement activities
        'daily_login': 5,
        'profile_complete': 25,
        'first_post': 15,
        'comment_create': 5,
        'like_give': 1,
        
        # Special activities
        'streak_milestone': lambda streak: streak * 10,  # Variable based on streak
        'referral': 50,
        'feedback_submit': 15,
    }
    
    points = 0
    category = 'activity'
    
    if activity_type in points_map:
        if callable(points_map[activity_type]):
            points = points_map[activity_type](activity_data.get('value', 1))
        else:
            points = points_map[activity_type]
        
        # Determine category
        if activity_type in ['club_join', 'club_create', 'club_leadership']:
            category = 'social'
        elif activity_type in ['event_register', 'event_attend', 'event_create', 'event_organize']:
            category = 'activity'
        elif activity_type in ['collaboration_join', 'collaboration_create', 'collaboration_complete']:
            category = 'leadership'
        elif activity_type in ['achievement_complete', 'milestone_complete']:
            category = 'academic'
        else:
            category = 'special'
        
        # Award points
        points_profile, created = UserPoints.objects.get_or_create(user=user)
        points_profile.add_points(points, category, f"Activity: {activity_type}")
        
        return points
    
    return 0


def check_user_badges(user):
    """Check if user has earned any new badges"""
    new_badges = []
    
    # Get user's points profile
    points_profile = getattr(user, 'points_profile', None)
    if not points_profile:
        return new_badges
    
    # Define badge requirements
    badge_requirements = {
        'first_steps': {
            'total_points__gte': 50,
            'description': 'Earn your first 50 points'
        },
        'point_collector': {
            'total_points__gte': 500,
            'description': 'Earn 500 total points'
        },
        'point_master': {
            'total_points__gte': 2000,
            'description': 'Earn 2000 total points'
        },
        'level_up': {
            'level__gte': 5,
            'description': 'Reach level 5'
        },
        'social_butterfly': {
            'social_points__gte': 200,
            'description': 'Earn 200 social points'
        },
        'leader': {
            'leadership_points__gte': 300,
            'description': 'Earn 300 leadership points'
        },
        'streak_starter': {
            'current_streak__gte': 7,
            'description': 'Maintain a 7-day activity streak'
        },
        'streak_master': {
            'current_streak__gte': 30,
            'description': 'Maintain a 30-day activity streak'
        },
        'club_enthusiast': {
            'custom_check': lambda u: u.joined_clubs.filter(memberships__status='active').count() >= 3,
            'description': 'Join 3 or more clubs'
        },
        'event_goer': {
            'custom_check': lambda u: u.event_registrations.filter(status='attended').count() >= 5,
            'description': 'Attend 5 or more events'
        },
        'collaborator': {
            'custom_check': lambda u: u.collaboration_participations.filter(
                status__in=['active', 'completed']
            ).count() >= 2,
            'description': 'Participate in 2 or more collaborations'
        }
    }
    
    # Check each badge requirement
    for badge_name, requirements in badge_requirements.items():
        try:
            # Check if badge exists and user doesn't already have it
            badge = Badge.objects.filter(name__icontains=badge_name, is_active=True).first()
            if not badge:
                continue
            
            if UserBadge.objects.filter(user=user, badge=badge).exists():
                continue
            
            # Check requirements
            earned = False
            
            if 'custom_check' in requirements:
                earned = requirements['custom_check'](user)
            else:
                # Check numeric requirements
                for field, value in requirements.items():
                    if field == 'description':
                        continue
                    
                    field_parts = field.split('__')
                    field_name = field_parts[0]
                    operator = field_parts[1] if len(field_parts) > 1 else 'exact'
                    
                    if hasattr(points_profile, field_name):
                        field_value = getattr(points_profile, field_name)
                        
                        if operator == 'gte' and field_value >= value:
                            earned = True
                        elif operator == 'lte' and field_value <= value:
                            earned = True
                        elif operator == 'exact' and field_value == value:
                            earned = True
                        else:
                            earned = False
                            break
            
            # Award badge if earned
            if earned:
                user_badge = UserBadge.objects.create(
                    user=user,
                    badge=badge,
                    earned_for=requirements.get('description', f'Earned {badge.name}')
                )
                new_badges.append(user_badge)
                
        except Exception as e:
            print(f"Error checking badge {badge_name}: {e}")
            continue
    
    return new_badges


def check_user_achievements(user, activity_type=None, activity_data=None):
    """Check and update user achievement progress"""
    achievement_updates = []
    
    # Get user's active achievements
    active_achievements = UserAchievement.objects.filter(
        user=user,
        status='in_progress'
    ).select_related('achievement')
    
    for user_achievement in active_achievements:
        achievement = user_achievement.achievement
        
        # Skip if achievement is not available
        if not achievement.is_available:
            continue
        
        # Update progress based on activity
        progress_updated = False
        
        if activity_type:
            # Map activities to achievement progress
            activity_progress_map = {
                'club_join': 'clubs_joined',
                'event_attend': 'events_attended', 
                'collaboration_complete': 'collaborations_completed',
                'daily_login': 'login_days',
                'achievement_complete': 'achievements_completed',
            }
            
            if activity_type in activity_progress_map:
                progress_key = activity_progress_map[activity_type]
                current_value = user_achievement.progress.get(progress_key, 0)
                user_achievement.progress[progress_key] = current_value + 1
                progress_updated = True
        
        # Calculate overall progress
        if progress_updated:
            user_achievement.update_progress(user_achievement.progress)
            achievement_updates.append({
                'achievement': achievement.name,
                'progress_percentage': user_achievement.progress_percentage,
                'status': user_achievement.status
            })
    
    return achievement_updates


def calculate_user_rankings():
    """Calculate and update user rankings"""
    from apps.authentication.models import User
    
    # Global rankings by points
    users_by_points = User.objects.filter(
        is_active=True,
        points_profile__isnull=False
    ).order_by('-points_profile__total_points')
    
    for rank, user in enumerate(users_by_points, 1):
        user.points_profile.global_rank = rank
        user.points_profile.save(update_fields=['global_rank'])
    
    # College rankings by points
    colleges = User.objects.filter(
        is_active=True,
        points_profile__isnull=False
    ).values('college_email_domain').distinct()
    
    for college_info in colleges:
        college_domain = college_info['college_email_domain']
        college_users = User.objects.filter(
            is_active=True,
            college_email_domain=college_domain,
            points_profile__isnull=False
        ).order_by('-points_profile__total_points')
        
        for rank, user in enumerate(college_users, 1):
            user.points_profile.college_rank = rank
            user.points_profile.save(update_fields=['college_rank'])


def get_user_engagement_score(user):
    """Calculate user engagement score"""
    if not hasattr(user, 'points_profile'):
        return 0
    
    points_profile = user.points_profile
    
    # Base score from points
    base_score = min(points_profile.total_points / 10, 100)  # Max 100 from points
    
    # Bonus from level
    level_bonus = points_profile.level * 5
    
    # Bonus from streak
    streak_bonus = min(points_profile.current_streak * 2, 50)  # Max 50 from streak
    
    # Bonus from badges
    badge_count = user.earned_badges.count()
    badge_bonus = min(badge_count * 5, 100)  # Max 100 from badges
    
    # Bonus from achievements
    completed_achievements = user.achievements.filter(status='completed').count()
    achievement_bonus = completed_achievements * 20
    
    # Recent activity bonus
    recent_activity = user.points_transactions.filter(
        created_at__gte=timezone.now() - timezone.timedelta(days=7)
    ).count()
    activity_bonus = min(recent_activity * 2, 30)  # Max 30 from recent activity
    
    total_score = base_score + level_bonus + streak_bonus + badge_bonus + achievement_bonus + activity_bonus
    
    return min(total_score, 1000)  # Cap at 1000


def create_default_badges():
    """Create default badges for the system"""
    default_badges = [
        {
            'name': 'First Steps',
            'description': 'Welcome to the platform! You\'ve taken your first steps.',
            'badge_type': 'milestone',
            'difficulty': 'bronze',
            'points_reward': 10,
            'requirements': {'total_points__gte': 10}
        },
        {
            'name': 'Point Collector',
            'description': 'You\'ve collected 500 points! Keep it up!',
            'badge_type': 'milestone',
            'difficulty': 'silver',
            'points_reward': 50,
            'requirements': {'total_points__gte': 500}
        },
        {
            'name': 'Point Master',
            'description': 'Amazing! You\'ve reached 2000 points!',
            'badge_type': 'milestone',
            'difficulty': 'gold',
            'points_reward': 200,
            'requirements': {'total_points__gte': 2000}
        },
        {
            'name': 'Social Butterfly',
            'description': 'You love connecting with others!',
            'badge_type': 'social',
            'difficulty': 'silver',
            'points_reward': 75,
            'requirements': {'social_points__gte': 200}
        },
        {
            'name': 'Leader',
            'description': 'Your leadership skills are shining!',
            'badge_type': 'leadership',
            'difficulty': 'gold',
            'points_reward': 150,
            'requirements': {'leadership_points__gte': 300}
        },
        {
            'name': 'Streak Starter',
            'description': 'You\'ve maintained a 7-day activity streak!',
            'badge_type': 'activity',
            'difficulty': 'bronze',
            'points_reward': 50,
            'requirements': {'current_streak__gte': 7}
        },
        {
            'name': 'Streak Master',
            'description': 'Incredible! 30 days of consistent activity!',
            'badge_type': 'activity',
            'difficulty': 'platinum',
            'points_reward': 300,
            'requirements': {'current_streak__gte': 30}
        },
        {
            'name': 'Club Enthusiast',
            'description': 'You\'re active in multiple clubs!',
            'badge_type': 'social',
            'difficulty': 'silver',
            'points_reward': 100,
            'requirements': {'clubs_joined__gte': 3}
        },
        {
            'name': 'Event Goer',
            'description': 'You love attending events!',
            'badge_type': 'activity',
            'difficulty': 'silver',
            'points_reward': 75,
            'requirements': {'events_attended__gte': 5}
        },
        {
            'name': 'Collaborator',
            'description': 'You excel at working with others!',
            'badge_type': 'leadership',
            'difficulty': 'gold',
            'points_reward': 200,
            'requirements': {'collaborations_completed__gte': 2}
        }
    ]
    
    for badge_data in default_badges:
        badge, created = Badge.objects.get_or_create(
            name=badge_data['name'],
            defaults=badge_data
        )
        if created:
            print(f"Created badge: {badge.name}")


def create_default_achievements():
    """Create default achievements for the system"""
    default_achievements = [
        {
            'name': 'First Month Champion',
            'description': 'Complete your first month on the platform with flying colors!',
            'achievement_type': 'challenge',
            'requirements': {
                'days_active': 20,
                'points_earned': 500,
                'clubs_joined': 2,
                'events_attended': 3
            },
            'points_reward': 1000,
            'is_featured': True
        },
        {
            'name': 'Social Network Builder',
            'description': 'Build your social network by connecting with clubs and events.',
            'achievement_type': 'milestone',
            'requirements': {
                'clubs_joined': 5,
                'events_attended': 10,
                'collaborations_joined': 1
            },
            'points_reward': 750
        },
        {
            'name': 'Leadership Journey',
            'description': 'Take on leadership roles and make a difference.',
            'achievement_type': 'milestone',
            'requirements': {
                'clubs_led': 1,
                'events_organized': 2,
                'collaborations_led': 1
            },
            'points_reward': 1500
        },
        {
            'name': 'Academic Excellence',
            'description': 'Demonstrate academic excellence through platform activities.',
            'achievement_type': 'milestone',
            'requirements': {
                'academic_points': 500,
                'study_groups_joined': 3,
                'academic_events_attended': 5
            },
            'points_reward': 1000
        }
    ]
    
    for achievement_data in default_achievements:
        achievement, created = Achievement.objects.get_or_create(
            name=achievement_data['name'],
            defaults=achievement_data
        )
        if created:
            print(f"Created achievement: {achievement.name}")
