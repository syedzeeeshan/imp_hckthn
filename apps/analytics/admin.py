"""
Django admin configuration for analytics app
Error-free admin interface for analytics management
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from django.utils import timezone
from .models import AnalyticsReport, DashboardWidget

@admin.register(AnalyticsReport)
class AnalyticsReportAdmin(admin.ModelAdmin):
    """Analytics Report admin with comprehensive management"""
    
    list_display = [
        'title', 'report_type', 'frequency', 'club_display', 'college_display',
        'status', 'generated_by', 'generation_duration_display', 'created_at'
    ]
    
    list_filter = [
        'report_type', 'frequency', 'status', 'is_scheduled', 'is_public',
        'created_at', 'generation_completed_at'
    ]
    
    search_fields = ['title', 'generated_by__full_name', 'club__name', 'college__name']
    
    readonly_fields = [
        'id', 'data_preview', 'summary_preview', 'status', 'error_message',
        'generation_started_at', 'generation_completed_at', 'generation_duration_display',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        (None, {
            'fields': ('title', 'report_type', 'frequency')
        }),
        ('Scope', {
            'fields': ('club', 'college', 'date_from', 'date_to', 'filters')
        }),
        ('Settings', {
            'fields': ('is_scheduled', 'is_public', 'next_generation_at')
        }),
        ('Generation Status', {
            'fields': ('status', 'error_message', 'generation_started_at', 
                      'generation_completed_at', 'generation_duration_display'),
            'classes': ('collapse',)
        }),
        ('Data Preview', {
            'fields': ('data_preview', 'summary_preview'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('generated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['regenerate_reports', 'mark_as_public', 'mark_as_private']
    
    def club_display(self, obj):
        """Display club name or 'All Clubs'"""
        return obj.club.name if obj.club else 'All Clubs'
    club_display.short_description = 'Club'
    
    def college_display(self, obj):
        """Display college name or 'All Colleges'"""
        return obj.college.name if obj.college else 'All Colleges'
    college_display.short_description = 'College'
    
    def generation_duration_display(self, obj):
        """Display generation duration"""
        if obj.generation_started_at and obj.generation_completed_at:
            duration = obj.generation_completed_at - obj.generation_started_at
            return f"{duration.total_seconds():.2f} seconds"
        return "Not completed"
    generation_duration_display.short_description = 'Generation Duration'
    
    def data_preview(self, obj):
        """Display data preview"""
        if obj.data:
            import json
            preview = json.dumps(obj.data, indent=2)[:1000]  # First 1000 chars
            if len(json.dumps(obj.data)) > 1000:
                preview += "\n... (truncated)"
            return format_html('<pre style="background: #f8f9fa; padding: 10px; max-height: 200px; overflow-y: auto;">{}</pre>', preview)
        return "No data generated"
    data_preview.short_description = 'Data Preview'
    
    def summary_preview(self, obj):
        """Display summary preview"""
        if obj.summary:
            import json
            preview = json.dumps(obj.summary, indent=2)
            return format_html('<pre style="background: #e9ecef; padding: 10px;">{}</pre>', preview)
        return "No summary available"
    summary_preview.short_description = 'Summary'
    
    def regenerate_reports(self, request, queryset):
        """Bulk regenerate reports"""
        regenerated_count = 0
        for report in queryset:
            try:
                report.generate_report()
                regenerated_count += 1
            except Exception as e:
                self.message_user(request, f'Failed to regenerate {report.title}: {str(e)}', level='ERROR')
        
        if regenerated_count > 0:
            self.message_user(request, f'Successfully regenerated {regenerated_count} reports.')
    regenerate_reports.short_description = "Regenerate selected reports"
    
    def mark_as_public(self, request, queryset):
        """Mark reports as public"""
        updated = queryset.update(is_public=True)
        self.message_user(request, f'{updated} reports marked as public.')
    mark_as_public.short_description = "Mark as public"
    
    def mark_as_private(self, request, queryset):
        """Mark reports as private"""
        updated = queryset.update(is_public=False)
        self.message_user(request, f'{updated} reports marked as private.')
    mark_as_private.short_description = "Mark as private"
    
    def get_queryset(self, request):
        """Filter based on user permissions"""
        qs = super().get_queryset(request).select_related(
            'club', 'college', 'generated_by'
        )
        
        if request.user.is_superuser:
            return qs
        
        # College admins see only their college reports
        if hasattr(request.user, 'user_type') and request.user.user_type == 'college_admin':
            return qs.filter(college__domain=request.user.college_email_domain)
        
        return qs.filter(generated_by=request.user)
    
    def save_model(self, request, obj, form, change):
        """Set generated_by on creation"""
        if not change:
            obj.generated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    """Dashboard Widget admin"""
    
    list_display = [
        'title', 'widget_type', 'data_source', 'user', 'club_display',
        'is_visible', 'is_shared', 'last_updated'
    ]
    
    list_filter = [
        'widget_type', 'is_visible', 'is_shared', 'auto_refresh',
        'created_at', 'last_updated'
    ]
    
    search_fields = ['title', 'user__full_name', 'club__name', 'data_source']
    
    readonly_fields = [
        'id', 'last_updated', 'grid_position_display', 'config_preview',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        (None, {
            'fields': ('title', 'widget_type', 'data_source')
        }),
        ('Configuration', {
            'fields': ('config_preview', 'filters'),
            'classes': ('collapse',)
        }),
        ('Layout', {
            'fields': ('grid_position_display', 'is_visible')
        }),
        ('Access Control', {
            'fields': ('user', 'club', 'is_shared')
        }),
        ('Refresh Settings', {
            'fields': ('auto_refresh', 'refresh_interval', 'last_updated')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['refresh_widgets', 'make_visible', 'make_hidden', 'enable_sharing']
    
    def club_display(self, obj):
        """Display club name or 'Global'"""
        return obj.club.name if obj.club else 'Global'
    club_display.short_description = 'Scope'
    
    def grid_position_display(self, obj):
        """Display grid position"""
        if obj.grid_position:
            return f"X: {obj.grid_position.get('x', 0)}, Y: {obj.grid_position.get('y', 0)}, W: {obj.grid_position.get('width', 1)}, H: {obj.grid_position.get('height', 1)}"
        return "Not positioned"
    grid_position_display.short_description = 'Grid Position'
    
    def config_preview(self, obj):
        """Display config preview"""
        if obj.config:
            import json
            preview = json.dumps(obj.config, indent=2)
            return format_html('<pre style="background: #f8f9fa; padding: 10px; max-height: 150px; overflow-y: auto;">{}</pre>', preview)
        return "No configuration"
    config_preview.short_description = 'Configuration'
    
    def refresh_widgets(self, request, queryset):
        """Refresh widget data"""
        for widget in queryset:
            widget.refresh_data()
        self.message_user(request, f'Refreshed {queryset.count()} widgets.')
    refresh_widgets.short_description = "Refresh selected widgets"
    
    def make_visible(self, request, queryset):
        """Make widgets visible"""
        updated = queryset.update(is_visible=True)
        self.message_user(request, f'{updated} widgets made visible.')
    make_visible.short_description = "Make visible"
    
    def make_hidden(self, request, queryset):
        """Hide widgets"""
        updated = queryset.update(is_visible=False)
        self.message_user(request, f'{updated} widgets hidden.')
    make_hidden.short_description = "Hide widgets"
    
    def enable_sharing(self, request, queryset):
        """Enable sharing for widgets"""
        updated = queryset.update(is_shared=True)
        self.message_user(request, f'{updated} widgets enabled for sharing.')
    enable_sharing.short_description = "Enable sharing"
    
    def get_queryset(self, request):
        """Filter based on user permissions"""
        qs = super().get_queryset(request).select_related('user', 'club')
        
        if request.user.is_superuser:
            return qs
        
        # Users see only their own widgets
        return qs.filter(user=request.user)


# Custom admin site configuration
from django.contrib.admin import AdminSite

class AnalyticsAdminSite(AdminSite):
    site_header = "Analytics Administration"
    site_title = "Analytics Admin"
    index_title = "Analytics Dashboard"

# Create custom admin instance (optional)
analytics_admin_site = AnalyticsAdminSite(name='analytics_admin')
