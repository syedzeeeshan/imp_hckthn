"""
Django admin configuration for clubs app
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import ClubCategory, Club, ClubMembership, ClubSettings, ClubAnnouncement

@admin.register(ClubCategory)
class ClubCategoryAdmin(admin.ModelAdmin):
    """Club Category admin"""
    
    list_display = ['name', 'total_clubs_display', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'total_clubs_display', 'created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'icon', 'color')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Statistics', {
            'fields': ('total_clubs_display',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def total_clubs_display(self, obj):
        return obj.total_clubs
    total_clubs_display.short_description = 'Total Clubs'


class ClubMembershipInline(admin.TabularInline):
    """Inline for club memberships"""
    model = ClubMembership
    extra = 0
    readonly_fields = ['requested_at', 'joined_at']
    fields = ['user', 'role', 'status', 'requested_at', 'joined_at', 'approved_by']


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    """Club admin"""
    
    list_display = [
        'name', 'category', 'college', 'status', 'member_count_display',
        'is_verified', 'created_at'
    ]
    
    list_filter = [
        'status', 'privacy', 'is_verified', 'category', 'college',
        'created_at'
    ]
    
    search_fields = ['name', 'description', 'college__name']
    readonly_fields = [
        'id', 'slug', 'member_count_display', 'leader_count_display',
        'activity_score', 'created_at', 'updated_at'
    ]
    
    inlines = [ClubMembershipInline]
    
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'category', 'college')
        }),
        ('Description', {
            'fields': ('short_description', 'description')
        }),
        ('Visual Assets', {
            'fields': ('logo', 'cover_image'),
            'classes': ('collapse',)
        }),
        ('Contact Information', {
            'fields': ('email', 'phone', 'website', 'social_links'),
            'classes': ('collapse',)
        }),
        ('Meeting Information', {
            'fields': ('meeting_location', 'meeting_schedule', 'meeting_days'),
            'classes': ('collapse',)
        }),
        ('Settings', {
            'fields': ('status', 'privacy', 'is_verified', 'requires_approval', 'max_members')
        }),
        ('Financial', {
            'fields': ('membership_fee', 'budget'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': (
                'member_count_display', 'leader_count_display', 'activity_score',
                'total_events', 'total_collaborations'
            ),
            'classes': ('collapse',)
        }),
        ('Management', {
            'fields': ('created_by',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def member_count_display(self, obj):
        return obj.member_count
    member_count_display.short_description = 'Members'
    
    def leader_count_display(self, obj):
        return obj.leader_count
    leader_count_display.short_description = 'Leaders'
    
    def get_queryset(self, request):
        """Filter based on user permissions"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        # College admins see only their college clubs
        if hasattr(request.user, 'user_type') and request.user.user_type == 'college_admin':
            return qs.filter(college__domain=request.user.college_email_domain)
        
        return qs


@admin.register(ClubMembership)
class ClubMembershipAdmin(admin.ModelAdmin):
    """Club Membership admin"""
    
    list_display = [
        'user', 'club', 'role', 'status', 'joined_at', 'events_attended'
    ]
    
    list_filter = [
        'role', 'status', 'joined_at', 'club__category'
    ]
    
    search_fields = [
        'user__full_name', 'user__email', 'club__name'
    ]
    
    readonly_fields = [
        'id', 'requested_at', 'events_attended', 'last_activity',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        (None, {
            'fields': ('user', 'club', 'role', 'status')
        }),
        ('Dates', {
            'fields': ('requested_at', 'joined_at', 'approved_by')
        }),
        ('Activity', {
            'fields': ('events_attended', 'last_activity'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Filter based on user permissions"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        if hasattr(request.user, 'user_type') and request.user.user_type == 'college_admin':
            return qs.filter(club__college__domain=request.user.college_email_domain)
        
        return qs


@admin.register(ClubSettings)
class ClubSettingsAdmin(admin.ModelAdmin):
    """Club Settings admin"""
    
    list_display = ['club', 'notify_new_members', 'show_member_list', 'require_event_approval']
    list_filter = ['notify_new_members', 'show_member_list', 'require_event_approval']
    search_fields = ['club__name']
    
    fieldsets = (
        ('Notifications', {
            'fields': ('notify_new_members', 'notify_events', 'notify_collaborations')
        }),
        ('Privacy', {
            'fields': ('show_member_list', 'show_contact_info', 'allow_member_invites')
        }),
        ('Events', {
            'fields': ('auto_approve_events', 'require_event_approval')
        }),
        ('Advanced', {
            'fields': ('custom_fields', 'calendar_sync', 'email_integration'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ClubAnnouncement)
class ClubAnnouncementAdmin(admin.ModelAdmin):
    """Club Announcement admin"""
    
    list_display = [
        'title', 'club', 'priority', 'is_published', 'views',
        'created_by', 'created_at'
    ]
    
    list_filter = [
        'priority', 'is_published', 'send_email', 'send_notification',
        'created_at'
    ]
    
    search_fields = ['title', 'content', 'club__name']
    readonly_fields = ['id', 'views', 'created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('club', 'title', 'content', 'priority')
        }),
        ('Target Audience', {
            'fields': ('target_all_members', 'target_roles')
        }),
        ('Publishing', {
            'fields': ('is_published', 'publish_at', 'expires_at')
        }),
        ('Notifications', {
            'fields': ('send_email', 'send_notification')
        }),
        ('Statistics', {
            'fields': ('views',),
            'classes': ('collapse',)
        }),
        ('Management', {
            'fields': ('created_by',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Filter based on user permissions"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        if hasattr(request.user, 'user_type') and request.user.user_type == 'college_admin':
            return qs.filter(club__college__domain=request.user.college_email_domain)
        
        return qs
