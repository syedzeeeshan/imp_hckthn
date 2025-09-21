"""
Gamification views for Campus Club Management Suite
Seamless API endpoints for points, badges, achievements, and leaderboards
"""
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta

from .models import (
    Badge, UserPoints, UserBadge, PointsTransaction, Achievement,
    UserAchievement, Leaderboard, PointsCategory
)
from .serializers import (
    BadgeSerializer, UserPointsSerializer, UserBadgeSerializer,
    PointsTransactionSerializer, AchievementSerializer, UserAchievementSerializer,
    LeaderboardSerializer, PointsCategorySerializer, UserProfileGamificationSerializer,
    PointsAwardSerializer, BadgeAwardSerializer, LeaderboardRequestSerializer,
    GamificationStatsSerializer
)
from apps.authentication.models import User
from .utils import award_points_for_activity, check_user_badges, check_user_achievements


class BadgeListView(generics.ListAPIView):
    """List all available badges"""
    
    serializer_class = BadgeSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = Badge.objects.filter(is_active=True)
        
        # Hide hidden badges unless user has earned them
        user = self.request.user
        if user.is_authenticated:
            user_earned_badges = user.earned_badges.values_list('badge_id', flat=True)
            queryset = queryset.filter(
                Q(is_hidden=False) | Q(id__in=user_earned_badges)
            )
        else:
            queryset = queryset.filter(is_hidden=False)
        
        # Filter by type
        badge_type = self.request.query_params.get('type')
        if badge_type:
            queryset = queryset.filter(badge_type=badge_type)
        
        # Filter by difficulty
        difficulty = self.request.query_params.get('difficulty')
        if difficulty:
            queryset = queryset.filter(difficulty=difficulty)
        
        return queryset.order_by('difficulty', 'name')


class BadgeDetailView(generics.RetrieveAPIView):
    """Badge detail view"""
    
    serializer_class = BadgeSerializer
    permission_classes = [AllowAny]
    lookup_field = 'id'
    
    def get_queryset(self):
        return Badge.objects.filter(is_active=True)


class UserPointsView(generics.RetrieveAPIView):
    """Get user's points profile"""
    
    serializer_class = UserPointsSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        user = self.request.user
        points_profile, created = UserPoints.objects.get_or_create(user=user)
        return points_profile


class UserBadgesView(generics.ListAPIView):
    """List user's earned badges"""
    
    serializer_class = UserBadgeSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user_id = self.kwargs.get('user_id')
        if user_id:
            try:
                from uuid import UUID
                user_uuid = UUID(user_id)
                user = User.objects.get(id=user_uuid, is_active=True)
            except (ValueError, User.DoesNotExist):
                return UserBadge.objects.none()
        else:
            user = self.request.user
        
        queryset = UserBadge.objects.filter(
            user=user, 
            is_visible=True
        ).select_related('badge').order_by('-earned_at')
        
        # Filter by badge type
        badge_type = self.request.query_params.get('type')
        if badge_type:
            queryset = queryset.filter(badge__badge_type=badge_type)
        
        return queryset


class PointsTransactionsView(generics.ListAPIView):
    """List user's points transactions"""
    
    serializer_class = PointsTransactionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = PointsTransaction.objects.filter(user=user).order_by('-created_at')
        
        # Filter by transaction type
        transaction_type = self.request.query_params.get('type')
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if date_from:
            try:
                from datetime import datetime
                date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__gte=date_from_parsed)
            except ValueError:
                pass
        
        if date_to:
            try:
                from datetime import datetime
                date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__lte=date_to_parsed)
            except ValueError:
                pass
        
        return queryset


class AchievementListView(generics.ListAPIView):
    """List all available achievements"""
    
    serializer_class = AchievementSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = Achievement.objects.filter(is_active=True)
        
        # Filter by type
        achievement_type = self.request.query_params.get('type')
        if achievement_type:
            queryset = queryset.filter(achievement_type=achievement_type)
        
        # Filter by availability
        show_available_only = self.request.query_params.get('available_only', 'false').lower() == 'true'
        if show_available_only:
            now = timezone.now()
            queryset = queryset.filter(
                Q(start_date__isnull=True) | Q(start_date__lte=now),
                Q(end_date__isnull=True) | Q(end_date__gte=now)
            )
        
        return queryset.order_by('-is_featured', 'name')


class AchievementDetailView(generics.RetrieveAPIView):
    """Achievement detail view"""
    
    serializer_class = AchievementSerializer
    permission_classes = [AllowAny]
    lookup_field = 'id'
    
    def get_queryset(self):
        return Achievement.objects.filter(is_active=True)


class UserAchievementsView(generics.ListAPIView):
    """List user's achievements"""
    
    serializer_class = UserAchievementSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user_id = self.kwargs.get('user_id')
        if user_id:
            try:
                from uuid import UUID
                user_uuid = UUID(user_id)
                user = User.objects.get(id=user_uuid, is_active=True)
            except (ValueError, User.DoesNotExist):
                return UserAchievement.objects.none()
        else:
            user = self.request.user
        
        queryset = UserAchievement.objects.filter(user=user).select_related('achievement')
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('-started_at')


class LeaderboardListView(generics.ListAPIView):
    """List available leaderboards"""
    
    serializer_class = LeaderboardSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        return Leaderboard.objects.filter(is_active=True).order_by('name')


class LeaderboardDetailView(generics.RetrieveAPIView):
    """Leaderboard detail view with data"""
    
    serializer_class = LeaderboardSerializer
    permission_classes = [AllowAny]
    lookup_field = 'id'
    
    def get_queryset(self):
        return Leaderboard.objects.filter(is_active=True)
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        
        # Add college and club context if provided
        college_id = self.request.query_params.get('college')
        club_id = self.request.query_params.get('club')
        
        if college_id:
            try:
                from uuid import UUID
                from apps.authentication.models import College
                college = College.objects.get(id=UUID(college_id))
                context['college'] = college
            except (ValueError, College.DoesNotExist):
                pass
        
        if club_id:
            try:
                from uuid import UUID
                from apps.clubs.models import Club
                club = Club.objects.get(id=UUID(club_id))
                context['club'] = club
            except (ValueError, Club.DoesNotExist):
                pass
        
        return context


class AwardPointsView(APIView):
    """Award points to a user (admin only)"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, user_id):
        # Check if user has permission to award points
        if not (hasattr(request.user, 'is_super_admin') and request.user.is_super_admin):
            return Response({
                'error': 'Only super admins can award points'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            from uuid import UUID
            user_uuid = UUID(user_id)
            user = User.objects.get(id=user_uuid, is_active=True)
        except (ValueError, User.DoesNotExist):
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = PointsAwardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        points_profile, created = UserPoints.objects.get_or_create(user=user)
        points_profile.add_points(
            serializer.validated_data['points'],
            serializer.validated_data['category'],
            serializer.validated_data.get('description', 'Admin awarded points')
        )
        
        return Response({
            'message': f'Successfully awarded {serializer.validated_data["points"]} points to {user.full_name}',
            'points_profile': UserPointsSerializer(points_profile).data
        }, status=status.HTTP_200_OK)


class AwardBadgeView(APIView):
    """Award badge to a user (admin only)"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, user_id):
        # Check permissions
        if not (hasattr(request.user, 'is_super_admin') and request.user.is_super_admin):
            return Response({
                'error': 'Only super admins can award badges'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            from uuid import UUID
            user_uuid = UUID(user_id)
            user = User.objects.get(id=user_uuid, is_active=True)
        except (ValueError, User.DoesNotExist):
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = BadgeAwardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            badge = Badge.objects.get(id=serializer.validated_data['badge_id'], is_active=True)
        except Badge.DoesNotExist:
            return Response({
                'error': 'Badge not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user already has this badge (and it's not repeatable)
        if not badge.is_repeatable and UserBadge.objects.filter(user=user, badge=badge).exists():
            return Response({
                'error': 'User already has this badge and it is not repeatable'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user_badge = UserBadge.objects.create(
            user=user,
            badge=badge,
            earned_for=serializer.validated_data.get('earned_for', 'Admin awarded badge')
        )
        
        return Response({
            'message': f'Successfully awarded {badge.name} badge to {user.full_name}',
            'user_badge': UserBadgeSerializer(user_badge).data
        }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_gamification_profile(request, user_id=None):
    """Get comprehensive gamification profile for a user"""
    if user_id:
        try:
            from uuid import UUID
            user_uuid = UUID(user_id)
            user = User.objects.get(id=user_uuid, is_active=True)
        except (ValueError, User.DoesNotExist):
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
    else:
        user = request.user
    
    # Get or create points profile
    points_profile, created = UserPoints.objects.get_or_create(user=user)
    
    serializer = UserProfileGamificationSerializer(user, context={'request': request})
    
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def leaderboard_data(request):
    """Get leaderboard data with flexible parameters"""
    serializer = LeaderboardRequestSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    
    data = serializer.validated_data
    leaderboard_type = data['leaderboard_type']
    time_period = data['time_period']
    limit = data['limit']
    college_filter = data['college_filter']
    club_filter = data.get('club_filter')
    
    # Base user queryset
    users = User.objects.filter(is_active=True).select_related('points_profile')
    
    # Apply college filter
    if college_filter and request.user.is_authenticated:
        users = users.filter(college_email_domain=request.user.college_email_domain)
    
    # Apply club filter
    if club_filter:
        try:
            from apps.clubs.models import Club
            club = Club.objects.get(id=club_filter)
            users = users.filter(
                joined_clubs__memberships__club=club,
                joined_clubs__memberships__status='active'
            )
        except Club.DoesNotExist:
            pass
    
    # Time period filtering (simplified for now)
    if time_period != 'all_time':
        now = timezone.now()
        if time_period == 'daily':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_period == 'weekly':
            start_date = now - timedelta(days=now.weekday())
        elif time_period == 'monthly':
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # For time-based filtering, we'd need to aggregate transactions
        # This is a simplified version
    
    # Order by leaderboard type
    if leaderboard_type == 'points':
        users = users.order_by('-points_profile__total_points')
    elif leaderboard_type == 'level':
        users = users.order_by('-points_profile__level', '-points_profile__experience_points')
    elif leaderboard_type == 'badges':
        users = users.annotate(badge_count=Count('earned_badges')).order_by('-badge_count')
    elif leaderboard_type == 'streak':
        users = users.order_by('-points_profile__current_streak', '-points_profile__longest_streak')
    
    users = users[:limit]
    
    # Format leaderboard data
    leaderboard_data = []
    for rank, user in enumerate(users, 1):
        value = 0
        if hasattr(user, 'points_profile') and user.points_profile:
            if leaderboard_type == 'points':
                value = user.points_profile.total_points
            elif leaderboard_type == 'level':
                value = user.points_profile.level
            elif leaderboard_type == 'streak':
                value = user.points_profile.current_streak
        
        if leaderboard_type == 'badges':
            value = getattr(user, 'badge_count', 0)
        
        leaderboard_data.append({
            'rank': rank,
            'user': {
                'id': str(user.id),
                'full_name': user.full_name,
                'email': user.email,
                'avatar_url': user.avatar_url if hasattr(user, 'avatar_url') else None
            },
            'value': value
        })
    
    return Response({
        'leaderboard_type': leaderboard_type,
        'time_period': time_period,
        'data': leaderboard_data,
        'total_entries': len(leaderboard_data)
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def track_activity(request):
    """Track user activity for gamification"""
    activity_type = request.data.get('activity_type')
    activity_data = request.data.get('activity_data', {})
    
    if not activity_type:
        return Response({
            'error': 'activity_type is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    user = request.user
    
    # Award points based on activity
    points_awarded = award_points_for_activity(user, activity_type, activity_data)
    
    # Check for new badge achievements
    new_badges = check_user_badges(user)
    
    # Check for achievement progress
    achievement_updates = check_user_achievements(user, activity_type, activity_data)
    
    response_data = {
        'message': 'Activity tracked successfully',
        'points_awarded': points_awarded,
        'new_badges': [BadgeSerializer(badge.badge).data for badge in new_badges],
        'achievement_updates': achievement_updates
    }
    
    return Response(response_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gamification_stats(request):
    """Get platform gamification statistics"""
    # Check if user has permission to view stats
    if not (hasattr(request.user, 'is_super_admin') and request.user.is_super_admin or
            hasattr(request.user, 'is_college_admin') and request.user.is_college_admin):
        return Response({
            'error': 'You do not have permission to view platform statistics'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Calculate statistics
    total_points_awarded = PointsTransaction.objects.filter(points__gt=0).aggregate(
        total=Sum('points')
    )['total'] or 0
    
    total_badges_earned = UserBadge.objects.count()
    total_active_users = User.objects.filter(is_active=True, points_profile__total_points__gt=0).count()
    total_achievements_completed = UserAchievement.objects.filter(status='completed').count()
    
    # Top performers (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    top_performers = User.objects.filter(
        is_active=True,
        points_transactions__created_at__gte=thirty_days_ago
    ).annotate(
        recent_points=Sum('points_transactions__points')
    ).order_by('-recent_points')[:10]
    
    # Recent activities
    recent_activities = PointsTransaction.objects.filter(
        created_at__gte=thirty_days_ago
    ).select_related('user').order_by('-created_at')[:20]
    
    # Engagement metrics
    engagement_metrics = {
        'daily_active_users': User.objects.filter(
            points_profile__last_activity_date=timezone.now().date()
        ).count(),
        'weekly_active_users': User.objects.filter(
            points_profile__last_activity_date__gte=timezone.now().date() - timedelta(days=7)
        ).count(),
        'average_points_per_user': total_points_awarded / total_active_users if total_active_users > 0 else 0,
        'average_badges_per_user': total_badges_earned / total_active_users if total_active_users > 0 else 0,
    }
    
    stats_data = {
        'total_points_awarded': total_points_awarded,
        'total_badges_earned': total_badges_earned,
        'total_active_users': total_active_users,
        'total_achievements_completed': total_achievements_completed,
        'top_performers': [
            {
                'user': {
                    'id': str(user.id),
                    'full_name': user.full_name,
                    'email': user.email
                },
                'recent_points': user.recent_points or 0
            }
            for user in top_performers
        ],
        'recent_activities': [
            {
                'user': {
                    'full_name': transaction.user.full_name
                },
                'points': transaction.points,
                'type': transaction.get_transaction_type_display(),
                'description': transaction.description,
                'created_at': transaction.created_at
            }
            for transaction in recent_activities
        ],
        'engagement_metrics': engagement_metrics
    }
    
    serializer = GamificationStatsSerializer(stats_data)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def join_achievement(request, achievement_id):
    """Join an achievement challenge"""
    try:
        from uuid import UUID
        achievement_uuid = UUID(achievement_id)
        achievement = Achievement.objects.get(id=achievement_uuid, is_active=True)
    except (ValueError, Achievement.DoesNotExist):
        return Response({
            'error': 'Achievement not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if not achievement.is_available:
        return Response({
            'error': 'Achievement is not currently available'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    user = request.user
    
    # Check if user is already participating
    if UserAchievement.objects.filter(user=user, achievement=achievement).exists():
        return Response({
            'error': 'You are already participating in this achievement'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Create user achievement
    user_achievement = UserAchievement.objects.create(
        user=user,
        achievement=achievement
    )
    
    # Update achievement participant count
    achievement.total_participants += 1
    achievement.save()
    
    return Response({
        'message': f'Successfully joined achievement: {achievement.name}',
        'user_achievement': UserAchievementSerializer(user_achievement).data
    }, status=status.HTTP_201_CREATED)
