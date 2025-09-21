"""
Django admin configuration for gamification app
Comprehensive admin interface for gamification management
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Sum
from django.utils import timezone
from .models import (
    Badge, UserBadge, UserPoints, PointsTransaction, Achievement,
    UserAchievement, Leaderboard, PointsCategory
)

@admin.register(PointsCategory)
class PointsCategoryAdmin(admin.ModelAdmin):
    """Points Category admin"""
    
    list_display = ['name', 'base_points', 'multiplier', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'icon', 'color')
        }),
        ('Points Configuration', {
            'fields': ('base_points', 'multiplier')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    """Badge admin with comprehensive management"""
    
    list_display = [
        'name', 'badge_type', 'difficulty', 'points_reward',
        'total_earned', 'rarity_percentage_display', 'is_active'
    ]
    
    list_filter = ['badge_type', 'difficulty', 'is_active', 'is_hidden', 'is_repeatable']
    search_fields = ['name', 'description']
    
    readonly_fields = ['id', 'total_earned', 'rarity_percentage_display', 'created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'badge_type', 'difficulty')
        }),
        ('Visual', {
            'fields': ('icon', 'icon_url', 'color')
        }),
        ('Requirements & Rewards', {
            'fields': ('requirements', 'points_reward')
        }),
        ('Settings', {
            'fields': ('is_active', 'is_hidden', 'is_repeatable')
        }),
        ('Statistics', {
            'fields': ('total_earned', 'rarity_percentage_display'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_badges', 'deactivate_badges', 'make_visible', 'make_hidden']
    
    def rarity_percentage_display(self, obj):
        percentage = obj.rarity_percentage
        if percentage < 1:
            color = '#ff0000'  # Red for very rare
        elif percentage < 5:
            color = '#ff8800'  # Orange for rare
        elif percentage < 20:
            color = '#0088ff'  # Blue for uncommon
        else:
            color = '#00aa00'  # Green for common
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.2f}%</span>',
            color, percentage
        )
    rarity_percentage_display.short_description = 'Rarity'
    
    def activate_badges(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} badges activated.')
    activate_badges.short_description = "Activate selected badges"
    
    def deactivate_badges(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} badges deactivated.')
    deactivate_badges.short_description = "Deactivate selected badges"
    
    def make_visible(self, request, queryset):
        updated = queryset.update(is_hidden=False)
        self.message_user(request, f'{updated} badges made visible.')
    make_visible.short_description = "Make badges visible"
    
    def make_hidden(self, request, queryset):
        updated = queryset.update(is_hidden=True)
        self.message_user(request, f'{updated} badges made hidden.')
    make_hidden.short_description = "Hide badges until earned"


@admin.register(UserPoints)
class UserPointsAdmin(admin.ModelAdmin):
    """User Points admin"""
    
    list_display = [
        'user', 'total_points', 'level', 'current_streak',
        'global_rank', 'college_rank', 'last_activity_date'
    ]
    
    list_filter = ['level', 'last_activity_date', 'created_at']
    search_fields = ['user__full_name', 'user__email']
    
    readonly_fields = [
        'id', 'total_points', 'lifetime_points', 'global_rank', 'college_rank',
        'level', 'experience_points', 'points_to_next_level', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Points Summary', {
            'fields': ('total_points', 'lifetime_points', 'level', 'experience_points', 'points_to_next_level')
        }),
        ('Category Breakdown', {
            'fields': ('activity_points', 'social_points', 'leadership_points', 'academic_points', 'special_points'),
            'classes': ('collapse',)
        }),
        ('Rankings', {
            'fields': ('global_rank', 'college_rank'),
            'classes': ('collapse',)
        }),
        ('Streaks', {
            'fields': ('current_streak', 'longest_streak', 'last_activity_date')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').order_by('-total_points')


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    """User Badge admin"""
    
    list_display = [
        'user', 'badge', 'earned_at', 'is_featured', 'is_visible'
    ]
    
    list_filter = ['badge__badge_type', 'badge__difficulty', 'is_featured', 'is_visible', 'earned_at']
    search_fields = ['user__full_name', 'user__email', 'badge__name']
    
    readonly_fields = ['id', 'earned_at', 'created_at']
    
    fieldsets = (
        (None, {
            'fields': ('user', 'badge', 'earned_for')
        }),
        ('Display Settings', {
            'fields': ('is_featured', 'is_visible')
        }),
        ('Timestamps', {
            'fields': ('earned_at', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'badge').order_by('-earned_at')


@admin.register(PointsTransaction)
class PointsTransactionAdmin(admin.ModelAdmin):
    """Points Transaction admin"""
    
    list_display = [
        'user', 'points', 'transaction_type', 'category',
        'balance_after', 'created_at'
    ]
    
    list_filter = ['transaction_type', 'category', 'created_at']
    search_fields = ['user__full_name', 'user__email', 'description']
    
    readonly_fields = ['id', 'balance_after', 'created_at']
    
    fieldsets = (
        (None, {
            'fields': ('user', 'points', 'transaction_type', 'category')
        }),
        ('Details', {
            'fields': ('description', 'related_object_type', 'related_object_id')
        }),
        ('Result', {
            'fields': ('balance_after',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').order_by('-created_at')
    
    def has_add_permission(self, request):
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    """Achievement admin"""
    
    list_display = [
        'name', 'achievement_type', 'points_reward', 'total_participants',
        'total_completed', 'completion_rate_display', 'is_active', 'is_featured'
    ]
    
    list_filter = ['achievement_type', 'is_active', 'is_featured', 'start_date', 'end_date']
    search_fields = ['name', 'description']
    
    readonly_fields = [
        'id', 'total_participants', 'total_completed', 'completion_rate_display',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'achievement_type')
        }),
        ('Requirements & Rewards', {
            'fields': ('requirements', 'points_reward', 'badge_reward')
        }),
        ('Timing', {
            'fields': ('start_date', 'end_date')
        }),
        ('Settings', {
            'fields': ('is_active', 'is_featured')
        }),
        ('Statistics', {
            'fields': ('total_participants', 'total_completed', 'completion_rate_display'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def completion_rate_display(self, obj):
        rate = obj.completion_rate
        if rate < 10:
            color = '#ff0000'  # Red for very hard
        elif rate < 30:
            color = '#ff8800'  # Orange for hard
        elif rate < 60:
            color = '#0088ff'  # Blue for moderate
        else:
            color = '#00aa00'  # Green for easy
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, rate
        )
    completion_rate_display.short_description = 'Completion Rate'


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    """User Achievement admin"""
    
    list_display = [
        'user', 'achievement', 'status', 'progress_percentage',
        'started_at', 'completed_at'
    ]
    
    list_filter = ['status', 'achievement__achievement_type', 'started_at', 'completed_at']
    search_fields = ['user__full_name', 'user__email', 'achievement__name']
    
    readonly_fields = ['id', 'started_at', 'completed_at']
    
    fieldsets = (
        (None, {
            'fields': ('user', 'achievement', 'status')
        }),
        ('Progress', {
            'fields': ('progress', 'progress_percentage')
        }),
        ('Timestamps', {
            'fields': ('started_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'achievement').order_by('-started_at')


@admin.register(Leaderboard)
class LeaderboardAdmin(admin.ModelAdmin):
    """Leaderboard admin"""
    
    list_display = [
        'name', 'leaderboard_type', 'time_period', 'college_specific',
        'club_specific', 'show_top_n', 'is_active'
    ]
    
    list_filter = ['leaderboard_type', 'time_period', 'college_specific', 'club_specific', 'is_active']
    search_fields = ['name', 'description']
    
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'leaderboard_type', 'time_period')
        }),
        ('Filtering', {
            'fields': ('college_specific', 'club_specific')
        }),
        ('Display Settings', {
            'fields': ('is_active', 'show_top_n')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# Custom admin actions
def award_points_bulk(modeladmin, request, queryset):
    """Bulk award points to selected users"""
    from .utils import award_points_for_activity
    
    points = 50  # Default points amount
    awarded_count = 0
    
    for user in queryset:
        try:
            points_profile, created = UserPoints.objects.get_or_create(user=user)
            points_profile.add_points(points, 'special', 'Bulk admin award')
            awarded_count += 1
        except Exception as e:
            continue
    
    modeladmin.message_user(request, f'Successfully awarded {points} points to {awarded_count} users.')

award_points_bulk.short_description = "Award 50 points to selected users"

# Add custom action to UserAdmin if it exists
try:
    from apps.authentication.admin import UserAdmin
    # Convert tuple to list, append, and reassign
    current_actions = list(getattr(UserAdmin, 'actions', []))
    current_actions.append(award_points_bulk)
    UserAdmin.actions = current_actions
except ImportError:
    pass
