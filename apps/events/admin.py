"""
Django admin configuration for events app
Comprehensive admin interface for event management
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Avg
from .models import (
    EventCategory, Event, EventRegistration, 
    EventResource, EventFeedback
)

@admin.register(EventCategory)
class EventCategoryAdmin(admin.ModelAdmin):
    """Event Category admin"""
    
    list_display = ['name', 'total_events_display', 'color_display', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'total_events_display', 'created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'icon', 'color')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Statistics', {
            'fields': ('total_events_display',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def total_events_display(self, obj):
        return obj.total_events
    total_events_display.short_description = 'Total Events'
    
    def color_display(self, obj):
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc;"></div>',
            obj.color
        )
    color_display.short_description = 'Color'


class EventRegistrationInline(admin.TabularInline):
    """Inline for event registrations"""
    model = EventRegistration
    extra = 0
    readonly_fields = ['created_at', 'checked_in_at', 'amount_paid']
    fields = ['user', 'status', 'payment_status', 'amount_paid', 'checked_in_at', 'feedback_rating']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


class EventResourceInline(admin.TabularInline):
    """Inline for event resources"""
    model = EventResource
    extra = 0
    readonly_fields = ['download_count', 'uploaded_by', 'created_at']
    fields = ['title', 'resource_type', 'file', 'external_url', 'is_public', 'uploaded_by']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """Event admin with comprehensive management"""
    
    list_display = [
        'title', 'club', 'event_type', 'start_datetime', 'status',
        'registration_count_display', 'attendance_count_display', 'created_by'
    ]
    
    list_filter = [
        'status', 'event_type', 'privacy', 'category', 'is_online',
        'start_datetime', 'created_at', 'club__college'
    ]
    
    search_fields = ['title', 'description', 'club__name', 'location']
    
    readonly_fields = [
        'id', 'slug', 'qr_code_display', 'total_registrations', 'total_attendees',
        'total_revenue', 'attendance_rate', 'registration_count_display',
        'attendance_count_display', 'average_rating_display', 'created_at', 'updated_at'
    ]
    
    inlines = [EventRegistrationInline, EventResourceInline]
    
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'event_type', 'category', 'club', 'created_by')
        }),
        ('Description', {
            'fields': ('short_description', 'description')
        }),
        ('Date & Time', {
            'fields': ('start_datetime', 'end_datetime', 'registration_deadline')
        }),
        ('Location', {
            'fields': ('location', 'venue_details', 'is_online', 'meeting_link')
        }),
        ('Media', {
            'fields': ('featured_image', 'qr_code_display'),
            'classes': ('collapse',)
        }),
        ('Registration', {
            'fields': ('max_attendees', 'registration_required', 'registration_fee', 'requires_approval')
        }),
        ('Settings', {
            'fields': ('status', 'privacy', 'is_active')
        }),
        ('Additional Information', {
            'fields': ('agenda', 'speakers', 'sponsors', 'tags', 'resources', 'external_links'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': (
                'total_registrations', 'total_attendees', 'total_revenue',
                'registration_count_display', 'attendance_count_display',
                'average_rating_display'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def registration_count_display(self, obj):
        count = obj.total_registrations
        if count > 0:
            url = reverse('admin:events_eventregistration_changelist') + f'?event__id__exact={obj.id}'
            return format_html('<a href="{}">{}</a>', url, count)
        return count
    registration_count_display.short_description = 'Registrations'
    
    def attendance_count_display(self, obj):
        count = obj.total_attendees
        if count > 0:
            url = reverse('admin:events_eventregistration_changelist') + f'?event__id__exact={obj.id}&status__exact=attended'
            return format_html('<a href="{}">{}</a>', url, count)
        return count
    attendance_count_display.short_description = 'Attendees'
    
    def qr_code_display(self, obj):
        if obj.qr_code:
            return format_html('<img src="{}" width="100" height="100" />', obj.qr_code.url)
        return "No QR Code"
    qr_code_display.short_description = 'QR Code'
    
    def average_rating_display(self, obj):
        avg = obj.feedback_entries.filter(is_approved=True).aggregate(
            avg_rating=Avg('overall_rating')
        )['avg_rating']
        if avg:
            return f"{avg:.1f}/5.0"
        return "No ratings"
    average_rating_display.short_description = 'Avg Rating'
    
    def get_queryset(self, request):
        """Filter based on user permissions"""
        qs = super().get_queryset(request).select_related('club', 'category', 'created_by')
        
        if request.user.is_superuser:
            return qs
        
        # College admins see only their college events
        if hasattr(request.user, 'user_type') and request.user.user_type == 'college_admin':
            return qs.filter(club__college__domain=request.user.college_email_domain)
        
        return qs


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    """Event Registration admin"""
    
    list_display = [
        'user', 'event', 'status', 'payment_status', 'amount_paid',
        'checked_in_at', 'feedback_rating', 'created_at'
    ]
    
    list_filter = [
        'status', 'payment_status', 'event__event_type', 'event__start_datetime',
        'checked_in_at', 'created_at'
    ]
    
    search_fields = [
        'user__full_name', 'user__email', 'event__title', 'event__club__name'
    ]
    
    readonly_fields = [
        'id', 'registration_data_display', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        (None, {
            'fields': ('user', 'event', 'status', 'payment_status')
        }),
        ('Payment', {
            'fields': ('amount_paid',)
        }),
        ('Check-in', {
            'fields': ('checked_in_at', 'checked_in_by', 'check_in_method')
        }),
        ('Feedback', {
            'fields': ('feedback_rating', 'feedback_comment', 'feedback_submitted_at'),
            'classes': ('collapse',)
        }),
        ('Additional Data', {
            'fields': ('registration_data_display',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def registration_data_display(self, obj):
        if obj.registration_data:
            import json
            return format_html('<pre>{}</pre>', json.dumps(obj.registration_data, indent=2))
        return "No additional data"
    registration_data_display.short_description = 'Registration Data'
    
    def get_queryset(self, request):
        """Filter based on user permissions"""
        qs = super().get_queryset(request).select_related('user', 'event', 'event__club')
        
        if request.user.is_superuser:
            return qs
        
        if hasattr(request.user, 'user_type') and request.user.user_type == 'college_admin':
            return qs.filter(event__club__college__domain=request.user.college_email_domain)
        
        return qs


@admin.register(EventResource)
class EventResourceAdmin(admin.ModelAdmin):
    """Event Resource admin"""
    
    list_display = [
        'title', 'event', 'resource_type', 'is_public', 'requires_registration',
        'download_count', 'uploaded_by', 'created_at'
    ]
    
    list_filter = [
        'resource_type', 'is_public', 'requires_registration', 'created_at'
    ]
    
    search_fields = ['title', 'description', 'event__title']
    
    readonly_fields = ['id', 'download_count', 'file_size_display', 'created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('event', 'title', 'description', 'resource_type')
        }),
        ('File/Link', {
            'fields': ('file', 'external_url', 'file_size_display')
        }),
        ('Access Control', {
            'fields': ('is_public', 'requires_registration')
        }),
        ('Statistics', {
            'fields': ('download_count',),
            'classes': ('collapse',)
        }),
        ('Management', {
            'fields': ('uploaded_by',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def file_size_display(self, obj):
        if obj.file:
            try:
                size = obj.file.size
                if size < 1024:
                    return f"{size} B"
                elif size < 1024 * 1024:
                    return f"{size / 1024:.1f} KB"
                elif size < 1024 * 1024 * 1024:
                    return f"{size / (1024 * 1024):.1f} MB"
                else:
                    return f"{size / (1024 * 1024 * 1024):.1f} GB"
            except Exception:
                return "Unknown size"
        return "No file"
    file_size_display.short_description = 'File Size'


@admin.register(EventFeedback)
class EventFeedbackAdmin(admin.ModelAdmin):
    """Event Feedback admin"""
    
    list_display = [
        'event', 'user_display', 'overall_rating', 'would_recommend',
        'is_anonymous', 'is_approved', 'created_at'
    ]
    
    list_filter = [
        'overall_rating', 'would_recommend', 'would_attend_again',
        'is_anonymous', 'is_approved', 'created_at'
    ]
    
    search_fields = ['event__title', 'user__full_name', 'comment']
    
    readonly_fields = ['id', 'registration', 'created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('event', 'user', 'registration')
        }),
        ('Ratings', {
            'fields': ('overall_rating', 'content_rating', 'organization_rating', 'venue_rating')
        }),
        ('Comments', {
            'fields': ('comment', 'suggestions')
        }),
        ('Recommendations', {
            'fields': ('would_recommend', 'would_attend_again')
        }),
        ('Additional Feedback', {
            'fields': ('additional_feedback',),
            'classes': ('collapse',)
        }),
        ('Settings', {
            'fields': ('is_anonymous', 'is_approved')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_display(self, obj):
        if obj.is_anonymous:
            return "Anonymous"
        return obj.user.full_name
    user_display.short_description = 'User'
    
    def get_queryset(self, request):
        """Filter based on user permissions"""
        qs = super().get_queryset(request).select_related('event', 'user', 'registration')
        
        if request.user.is_superuser:
            return qs
        
        if hasattr(request.user, 'user_type') and request.user.user_type == 'college_admin':
            return qs.filter(event__club__college__domain=request.user.college_email_domain)
        
        return qs


# Custom admin actions
def approve_registrations(modeladmin, request, queryset):
    """Bulk approve registrations"""
    approved_count = 0
    for registration in queryset.filter(status='pending'):
        if registration.approve_membership(request.user):
            approved_count += 1
    
    modeladmin.message_user(request, f'{approved_count} registrations approved successfully.')

approve_registrations.short_description = "Approve selected registrations"

def check_in_attendees(modeladmin, request, queryset):
    """Bulk check-in attendees"""
    checked_in_count = 0
    for registration in queryset.filter(status='registered'):
        if registration.check_in(checked_in_by=request.user, method='admin_bulk'):
            checked_in_count += 1
    
    modeladmin.message_user(request, f'{checked_in_count} attendees checked in successfully.')

check_in_attendees.short_description = "Check in selected attendees"

def approve_feedback(modeladmin, request, queryset):
    """Bulk approve feedback"""
    updated = queryset.update(is_approved=True)
    modeladmin.message_user(request, f'{updated} feedback entries approved successfully.')

approve_feedback.short_description = "Approve selected feedback"

# Add actions to admin classes
EventRegistrationAdmin.actions = [approve_registrations, check_in_attendees]
EventFeedbackAdmin.actions = [approve_feedback]
