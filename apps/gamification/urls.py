"""
URL patterns for gamification app
Complete endpoint routing for points, badges, achievements, and leaderboards
"""
from django.urls import path
from . import views

app_name = 'gamification'

urlpatterns = [
    # Badges
    path('badges/', views.BadgeListView.as_view(), name='badge_list'),
    path('badges/<uuid:id>/', views.BadgeDetailView.as_view(), name='badge_detail'),
    
    # User Points and Profile
    path('points/my-profile/', views.UserPointsView.as_view(), name='my_points'),
    path('points/transactions/', views.PointsTransactionsView.as_view(), name='points_transactions'),
    
    # User Badges
    path('badges/my-badges/', views.UserBadgesView.as_view(), name='my_badges'),
    path('badges/user/<uuid:user_id>/', views.UserBadgesView.as_view(), name='user_badges'),
    
    # Achievements
    path('achievements/', views.AchievementListView.as_view(), name='achievement_list'),
    path('achievements/<uuid:id>/', views.AchievementDetailView.as_view(), name='achievement_detail'),
    path('achievements/<uuid:achievement_id>/join/', views.join_achievement, name='join_achievement'),
    
    # User Achievements
    path('achievements/my-achievements/', views.UserAchievementsView.as_view(), name='my_achievements'),
    path('achievements/user/<uuid:user_id>/', views.UserAchievementsView.as_view(), name='user_achievements'),
    
    # Leaderboards
    path('leaderboards/', views.LeaderboardListView.as_view(), name='leaderboard_list'),
    path('leaderboards/<uuid:id>/', views.LeaderboardDetailView.as_view(), name='leaderboard_detail'),
    path('leaderboards/data/', views.leaderboard_data, name='leaderboard_data'),
    
    # Admin Actions
    path('admin/award-points/<uuid:user_id>/', views.AwardPointsView.as_view(), name='award_points'),
    path('admin/award-badge/<uuid:user_id>/', views.AwardBadgeView.as_view(), name='award_badge'),
    
    # User Profile
    path('profile/', views.user_gamification_profile, name='my_gamification_profile'),
    path('profile/<uuid:user_id>/', views.user_gamification_profile, name='user_gamification_profile'),
    
    # Activity Tracking
    path('track-activity/', views.track_activity, name='track_activity'),
    
    # Statistics
    path('stats/', views.gamification_stats, name='gamification_stats'),
]
