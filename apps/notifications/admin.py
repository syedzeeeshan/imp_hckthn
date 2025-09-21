"""
Django admin configuration for notifications app
Comprehensive admin interface for notification management
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from django.utils import timezone
from .models import (
    NotificationType, NotificationSettings, Notification,
    NotificationBatch, PushNotificationDevice
)

@admin.register(NotificationType)
class NotificationTypeAdmin(admin.ModelAdmin):
    """Notification Type admin"""
    
    list_display = [
        'name', 'priority', 'color_display', 'default_enabled',
        'notification_count', 'is_active', 'created_at'
    ]
    
    list_filter = ['priority', 'is_active', 'default_enabled', 'created_at']
    search_fields = ['name', 'description']
    
    readonly_fields = ['id', 'notification_count', 'created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'icon', 'color')
        }),
        ('Default Settings', {
            'fields': ('default_enabled', 'default_email_enabled', 
                      'default_push_enabled', 'default_in_app_enabled')
        }),
        ('Configuration', {
            'fields': ('priority', 'is_active')
        }),
        ('Statistics', {
            'fields': ('notification_count',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def color_display(self, obj):
        return format_html(
            '<span style="background-color: {}; padding: 2px 8px; border-radius: 3px; color: white;">{}</span>',
            obj.color, obj.color
        )
    color_display.short_description = 'Color'
    
    def notification_count(self, obj):
        return obj.notifications.count()
    notification_count.short_description = 'Total Notifications'


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    """Notification Settings admin"""
    
    list_display = [
        'user', 'notifications_enabled', 'email_notifications_enabled',
        'push_notifications_enabled', 'email_frequency', 'quiet_hours_enabled'
    ]
    
    list_filter = [
        'notifications_enabled', 'email_notifications_enabled', 
        'push_notifications_enabled', 'email_frequency', 'quiet_hours_enabled'
    ]
    
    search_fields = ['user__full_name', 'user__email']
    
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Global Settings', {
            'fields': ('notifications_enabled', 'email_notifications_enabled',
                      'push_notifications_enabled', 'in_app_notifications_enabled')
        }),
        ('Email Settings', {
            'fields': ('email_frequency',)
        }),
        ('Quiet Hours', {
            'fields': ('quiet_hours_enabled', 'quiet_hours_start', 'quiet_hours_end')
        }),
        ('Type-Specific Settings', {
            'fields': ('type_settings',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Notification admin"""
    
    list_display = [
        'title_display', 'recipient', 'notification_type', 'priority_display',
        'status', 'delivery_status', 'created_at'
    ]
    
    list_filter = [
        'notification_type', 'priority', 'status', 'send_email', 'send_push',
        'email_sent', 'push_sent', 'created_at'
    ]
    
    search_fields = ['title', 'message', 'recipient__full_name', 'sender__full_name']
    
    readonly_fields = [
        'id', 'time_since_created', 'is_read', 'related_object_display',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        (None, {
            'fields': ('recipient', 'sender', 'notification_type', 'priority')
        }),
        ('Content', {
            'fields': ('title', 'message', 'action_url', 'data')
        }),
        ('Related Object', {
            'fields': ('related_object_type', 'related_object_id', 'related_object_display'),
            'classes': ('collapse',)
        }),
        ('Delivery Settings', {
            'fields': ('send_email', 'send_push', 'send_in_app')
        }),
        ('Status', {
            'fields': ('status', 'error_message', 'retry_count', 'max_retries')
        }),
        ('Delivery Status', {
            'fields': ('email_sent', 'push_sent', 'in_app_sent')
        }),
        ('Timestamps', {
            'fields': ('scheduled_at', 'sent_at', 'delivered_at', 'read_at', 
                      'expires_at', 'time_since_created')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_sent', 'mark_as_read', 'resend_failed']
    
    def title_display(self, obj):
        if len(obj.title) > 50:
            return obj.title[:50] + "..."
        return obj.title
    title_display.short_description = 'Title'
    
    def priority_display(self, obj):
        colors = {1: '#dc3545', 2: '#ffc107', 3: '#28a745'}
        labels = {1: 'High', 2: 'Medium', 3: 'Low'}
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.priority, '#6c757d'),
            labels.get(obj.priority, 'Unknown')
        )
    priority_display.short_description = 'Priority'
    
    def delivery_status(self, obj):
        statuses = []
        if obj.email_sent:
            statuses.append('📧')
        if obj.push_sent:
            statuses.append('📱')
        if obj.in_app_sent:
            statuses.append('🔔')
        return ' '.join(statuses) if statuses else '❌'
    delivery_status.short_description = 'Delivered'
    
    def related_object_display(self, obj):
        related_obj = obj.get_related_object()
        if related_obj:
            return f"{obj.related_object_type}: {str(related_obj)}"
        return "None"
    related_object_display.short_description = 'Related Object'
    
    def mark_as_sent(self, request, queryset):
        updated = queryset.update(status='sent', sent_at=timezone.now())
        self.message_user(request, f'{updated} notifications marked as sent.')
    mark_as_sent.short_description = "Mark as sent"
    
    def mark_as_read(self, request, queryset):
        updated = queryset.update(status='read', read_at=timezone.now())
        self.message_user(request, f'{updated} notifications marked as read.')
    mark_as_read.short_description = "Mark as read"
    
    def resend_failed(self, request, queryset):
        from .utils import send_notification
        resent_count = 0
        
        for notification in queryset.filter(status='failed'):
            if notification.can_retry():
                if send_notification(notification):
                    resent_count += 1
        
        self.message_user(request, f'{resent_count} notifications resent successfully.')
    resend_failed.short_description = "Resend failed notifications"


@admin.register(PushNotificationDevice)
class PushNotificationDeviceAdmin(admin.ModelAdmin):
    """Push Notification Device admin"""
    
    list_display = ['user', 'device_type', 'device_name', 'is_active', 'last_used_at']
    list_filter = ['device_type', 'is_active', 'created_at']
    search_fields = ['user__full_name', 'device_name', 'device_token']
    
    readonly_fields = ['id', 'last_used_at', 'created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('user', 'device_type', 'device_name')
        }),
        ('Device Info', {
            'fields': ('device_token', 'is_active')
        }),
        ('Activity', {
            'fields': ('last_used_at',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(NotificationBatch)
class NotificationBatchAdmin(admin.ModelAdmin):
    """Notification Batch admin"""
    
    list_display = [
        'name', 'notification_type', 'total_recipients', 'sent_count',
        'failed_count', 'status', 'created_by', 'created_at'
    ]
    
    list_filter = ['status', 'notification_type', 'created_at']
    search_fields = ['name', 'description', 'created_by__full_name']
    
    readonly_fields = [
        'id', 'total_recipients', 'sent_count', 'failed_count',
        'created_at', 'sent_at'
    ]
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'notification_type')
        }),
        ('Content', {
            'fields': ('title_template', 'message_template')
        }),
        ('Recipients', {
            'fields': ('recipients', 'total_recipients')
        }),
        ('Settings', {
            'fields': ('scheduled_at', 'priority', 'send_email', 'send_push', 'send_in_app')
        }),
        ('Status', {
            'fields': ('status', 'sent_count', 'failed_count')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'sent_at'),
            'classes': ('collapse',)
        }),
    )
    
    filter_horizontal = ['recipients']
