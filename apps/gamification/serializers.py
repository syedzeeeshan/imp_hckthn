"""
Gamification serializers for Campus Club Management Suite
Seamless API serialization for points, badges, achievements, and leaderboards
"""
from rest_framework import serializers
from django.utils import timezone
from django.db.models import Count, Avg, Sum
from apps.authentication.serializers import UserSerializer
from .models import (
    Badge, UserPoints, UserBadge, PointsTransaction, Achievement,
    UserAchievement, Leaderboard, PointsCategory
)

class PointsCategorySerializer(serializers.ModelSerializer):
    """Serializer for PointsCategory model"""
    
    class Meta:
        model = PointsCategory
        fields = [
            'id', 'name', 'description', 'icon', 'color', 'is_active',
            'base_points', 'multiplier', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class BadgeSerializer(serializers.ModelSerializer):
    """Serializer for Badge model"""
    
    rarity_percentage = serializers.ReadOnlyField()
    earned_by_user = serializers.SerializerMethodField()
    
    class Meta:
        model = Badge
        fields = [
            'id', 'name', 'description', 'badge_type', 'difficulty',
            'icon', 'icon_url', 'color', 'requirements', 'points_reward',
            'is_active', 'is_hidden', 'is_repeatable', 'total_earned',
            'rarity_percentage', 'earned_by_user', 'created_at'
        ]
        read_only_fields = [
            'id', 'total_earned', 'rarity_percentage', 'earned_by_user', 'created_at'
        ]
    
    def get_earned_by_user(self, obj):
        """Check if current user has earned this badge"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.earned_by.filter(user=request.user).exists()
        return False


class UserBadgeSerializer(serializers.ModelSerializer):
    """Serializer for UserBadge model"""
    
    badge = BadgeSerializer(read_only=True)
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = UserBadge
        fields = [
            'id', 'badge', 'user', 'earned_at', 'earned_for',
            'is_featured', 'is_visible', 'created_at'
        ]
        read_only_fields = ['id', 'badge', 'user', 'earned_at', 'created_at']


class PointsTransactionSerializer(serializers.ModelSerializer):
    """Serializer for PointsTransaction model"""
    
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = PointsTransaction
        fields = [
            'id', 'user', 'points', 'transaction_type', 'category',
            'description', 'related_object_type', 'related_object_id',
            'balance_after', 'created_at'
        ]
        read_only_fields = [
            'id', 'user', 'related_object_type', 'related_object_id',
            'balance_after', 'created_at'
        ]


class UserPointsSerializer(serializers.ModelSerializer):
    """Serializer for UserPoints model"""
    
    user = UserSerializer(read_only=True)
    recent_transactions = serializers.SerializerMethodField()
    level_progress_percentage = serializers.SerializerMethodField()
    next_level_points = serializers.SerializerMethodField()
    
    class Meta:
        model = UserPoints
        fields = [
            'id', 'user', 'total_points', 'lifetime_points', 'activity_points',
            'social_points', 'leadership_points', 'academic_points', 'special_points',
            'global_rank', 'college_rank', 'current_streak', 'longest_streak',
            'last_activity_date', 'level', 'experience_points', 'points_to_next_level',
            'level_progress_percentage', 'next_level_points', 'recent_transactions',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'total_points', 'lifetime_points', 'activity_points',
            'social_points', 'leadership_points', 'academic_points', 'special_points',
            'global_rank', 'college_rank', 'current_streak', 'longest_streak',
            'last_activity_date', 'level', 'experience_points', 'points_to_next_level',
            'level_progress_percentage', 'next_level_points', 'recent_transactions',
            'created_at', 'updated_at'
        ]
    
    def get_recent_transactions(self, obj):
        """Get recent points transactions"""
        transactions = obj.user.points_transactions.order_by('-created_at')[:5]
        return PointsTransactionSerializer(transactions, many=True).data
    
    def get_level_progress_percentage(self, obj):
        """Calculate progress to next level as percentage"""
        if obj.points_to_next_level == 0:
            return 100
        
        total_needed = obj._calculate_next_level_requirement()
        earned = total_needed - obj.points_to_next_level
        return round((earned / total_needed) * 100, 1)
    
    def get_next_level_points(self, obj):
        """Get points needed for next level"""
        return obj.points_to_next_level


class AchievementSerializer(serializers.ModelSerializer):
    """Serializer for Achievement model"""
    
    completion_rate = serializers.ReadOnlyField()
    is_available = serializers.ReadOnlyField()
    user_progress = serializers.SerializerMethodField()
    badge_reward = BadgeSerializer(read_only=True)
    
    class Meta:
        model = Achievement
        fields = [
            'id', 'name', 'description', 'achievement_type', 'requirements',
            'points_reward', 'badge_reward', 'start_date', 'end_date',
            'is_active', 'is_featured', 'total_participants', 'total_completed',
            'completion_rate', 'is_available', 'user_progress', 'created_at'
        ]
        read_only_fields = [
            'id', 'total_participants', 'total_completed', 'completion_rate',
            'is_available', 'user_progress', 'created_at'
        ]
    
    def get_user_progress(self, obj):
        """Get current user's progress on this achievement"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            progress = obj.user_progress.filter(user=request.user).first()
            if progress:
                return UserAchievementSerializer(progress).data
        return None


class UserAchievementSerializer(serializers.ModelSerializer):
    """Serializer for UserAchievement model"""
    
    achievement = AchievementSerializer(read_only=True)
    user = UserSerializer(read_only=True)
    days_active = serializers.SerializerMethodField()
    
    class Meta:
        model = UserAchievement
        fields = [
            'id', 'achievement', 'user', 'status', 'progress',
            'progress_percentage', 'started_at', 'completed_at', 'days_active'
        ]
        read_only_fields = [
            'id', 'achievement', 'user', 'started_at', 'completed_at', 'days_active'
        ]
    
    def get_days_active(self, obj):
        """Calculate days since achievement started"""
        if obj.completed_at:
            return (obj.completed_at - obj.started_at).days
        else:
            return (timezone.now() - obj.started_at).days


class LeaderboardSerializer(serializers.ModelSerializer):
    """Serializer for Leaderboard model"""
    
    leaderboard_data = serializers.SerializerMethodField()
    
    class Meta:
        model = Leaderboard
        fields = [
            'id', 'name', 'description', 'leaderboard_type', 'time_period',
            'college_specific', 'club_specific', 'is_active', 'show_top_n',
            'leaderboard_data', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'leaderboard_data', 'created_at', 'updated_at']
    
    def get_leaderboard_data(self, obj):
        """Get leaderboard data"""
        request = self.context.get('request')
        college = self.context.get('college')
        club = self.context.get('club')
        
        users = obj.get_leaderboard_data(college=college, club=club, limit=20)  # Top 20 for API
        
        leaderboard_data = []
        for rank, user in enumerate(users, 1):
            user_data = {
                'rank': rank,
                'user': UserSerializer(user).data,
                'value': self._get_user_leaderboard_value(obj, user)
            }
            leaderboard_data.append(user_data)
        
        return leaderboard_data
    
    def _get_user_leaderboard_value(self, leaderboard, user):
        """Get the value for this user on this leaderboard"""
        if not hasattr(user, 'points_profile'):
            return 0
        
        if leaderboard.leaderboard_type == 'points':
            return user.points_profile.total_points
        elif leaderboard.leaderboard_type == 'level':
            return user.points_profile.level
        elif leaderboard.leaderboard_type == 'badges':
            return user.earned_badges.count()
        elif leaderboard.leaderboard_type == 'streak':
            return user.points_profile.current_streak
        
        return 0


class UserProfileGamificationSerializer(serializers.Serializer):
    """Comprehensive gamification profile for a user"""
    
    points_profile = UserPointsSerializer(read_only=True)
    recent_badges = serializers.SerializerMethodField()
    active_achievements = serializers.SerializerMethodField()
    leaderboard_positions = serializers.SerializerMethodField()
    statistics = serializers.SerializerMethodField()
    
    def get_recent_badges(self, user):
        """Get recently earned badges"""
        recent_badges = user.earned_badges.select_related('badge').order_by('-earned_at')[:5]
        return UserBadgeSerializer(recent_badges, many=True).data
    
    def get_active_achievements(self, user):
        """Get achievements in progress"""
        active_achievements = user.achievements.filter(status='in_progress').select_related('achievement')
        return UserAchievementSerializer(active_achievements, many=True).data
    
    def get_leaderboard_positions(self, user):
        """Get user's positions on various leaderboards"""
        if not hasattr(user, 'points_profile'):
            return {}
        
        return {
            'global_points_rank': user.points_profile.global_rank,
            'college_rank': user.points_profile.college_rank,
            'level': user.points_profile.level,
            'total_badges': user.earned_badges.count(),
            'current_streak': user.points_profile.current_streak,
        }
    
    def get_statistics(self, user):
        """Get comprehensive statistics"""
        if not hasattr(user, 'points_profile'):
            return {}
        
        points_profile = user.points_profile
        
        # Badge statistics
        badges_by_difficulty = user.earned_badges.values('badge__difficulty').annotate(count=Count('id'))
        badge_difficulty_counts = {item['badge__difficulty']: item['count'] for item in badges_by_difficulty}
        
        # Activity statistics
        recent_activity = user.points_transactions.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=30)
        )
        
        return {
            'total_points': points_profile.total_points,
            'lifetime_points': points_profile.lifetime_points,
            'level': points_profile.level,
            'total_badges': user.earned_badges.count(),
            'badge_breakdown': badge_difficulty_counts,
            'longest_streak': points_profile.longest_streak,
            'current_streak': points_profile.current_streak,
            'points_this_month': recent_activity.aggregate(total=Sum('points'))['total'] or 0,
            'transactions_this_month': recent_activity.count(),
            'achievements_completed': user.achievements.filter(status='completed').count(),
            'achievements_in_progress': user.achievements.filter(status='in_progress').count(),
        }


class PointsAwardSerializer(serializers.Serializer):
    """Serializer for awarding points"""
    
    points = serializers.IntegerField(min_value=1, max_value=10000)
    category = serializers.ChoiceField(choices=[
        ('activity', 'Activity'),
        ('social', 'Social'),
        ('leadership', 'Leadership'),
        ('academic', 'Academic'),
        ('special', 'Special'),
    ], default='activity')
    description = serializers.CharField(max_length=200, required=False, allow_blank=True)
    
    def validate_points(self, value):
        """Validate points amount"""
        if value <= 0:
            raise serializers.ValidationError("Points must be positive")
        return value


class BadgeAwardSerializer(serializers.Serializer):
    """Serializer for awarding badges"""
    
    badge_id = serializers.UUIDField()
    earned_for = serializers.CharField(max_length=200, required=False, allow_blank=True)
    
    def validate_badge_id(self, value):
        """Validate badge exists and is active"""
        try:
            badge = Badge.objects.get(id=value, is_active=True)
            return value
        except Badge.DoesNotExist:
            raise serializers.ValidationError("Invalid badge selected")


class LeaderboardRequestSerializer(serializers.Serializer):
    """Serializer for leaderboard data requests"""
    
    leaderboard_type = serializers.ChoiceField(choices=[
        ('points', 'Points'),
        ('level', 'Level'),
        ('badges', 'Badges'),
        ('streak', 'Streak'),
    ])
    time_period = serializers.ChoiceField(
        choices=[
            ('all_time', 'All Time'),
            ('monthly', 'Monthly'),
            ('weekly', 'Weekly'),
            ('daily', 'Daily'),
        ],
        default='all_time'
    )
    limit = serializers.IntegerField(min_value=10, max_value=100, default=20)
    college_filter = serializers.BooleanField(default=False)
    club_filter = serializers.UUIDField(required=False)


class GamificationStatsSerializer(serializers.Serializer):
    """Serializer for gamification platform statistics"""
    
    total_points_awarded = serializers.IntegerField()
    total_badges_earned = serializers.IntegerField()
    total_active_users = serializers.IntegerField()
    total_achievements_completed = serializers.IntegerField()
    top_performers = serializers.ListField()
    recent_activities = serializers.ListField()
    engagement_metrics = serializers.DictField()
