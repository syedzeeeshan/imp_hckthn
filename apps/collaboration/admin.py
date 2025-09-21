"""
Django admin configuration for collaboration app
Comprehensive admin interface for collaboration management
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Avg
from django.utils import timezone
from .models import (
    CollaborationType, Collaboration, CollaborationParticipation,
    CollaborationMilestone, CollaborationMessage, CollaborationResource
)

@admin.register(CollaborationType)
class CollaborationTypeAdmin(admin.ModelAdmin):
    """Collaboration Type admin"""
    
    list_display = [
        'name', 'total_collaborations_display', 'min_participants', 
        'max_participants', 'requires_approval', 'is_active', 'created_at'
    ]
    
    list_filter = ['is_active', 'requires_approval', 'created_at']
    search_fields = ['name', 'description']
    
    readonly_fields = ['id', 'total_collaborations_display', 'created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'icon', 'color')
        }),
        ('Requirements', {
            'fields': ('min_participants', 'max_participants', 'requires_approval')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Statistics', {
            'fields': ('total_collaborations_display',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def total_collaborations_display(self, obj):
        return obj.total_collaborations
    total_collaborations_display.short_description = 'Total Collaborations'


class CollaborationParticipationInline(admin.TabularInline):
    """Inline for collaboration participations"""
    model = CollaborationParticipation
    extra = 0
    readonly_fields = ['created_at', 'joined_at', 'contribution_score']
    fields = [
        'club', 'status', 'role', 'committed_members', 
        'primary_contact', 'approved_by', 'contribution_score'
    ]


class CollaborationMilestoneInline(admin.TabularInline):
    """Inline for collaboration milestones"""
    model = CollaborationMilestone
    extra = 0
    readonly_fields = ['created_at', 'completed_at']
    fields = ['title', 'due_date', 'status', 'progress_percentage', 'assigned_by']


@admin.register(Collaboration)
class CollaborationAdmin(admin.ModelAdmin):
    """Collaboration admin with comprehensive management"""
    
    list_display = [
        'title', 'collaboration_type', 'initiator_club', 'status', 'priority',
        'participant_count_display', 'progress_percentage', 'start_date', 'created_by'
    ]
    
    list_filter = [
        'status', 'priority', 'privacy', 'collaboration_type',
        'allows_external_participants', 'start_date', 'created_at'
    ]
    
    search_fields = ['title', 'description', 'initiator_club__name', 'created_by__full_name']
    
    readonly_fields = [
        'id', 'slug', 'total_participants', 'total_applications', 'success_rating',
        'participant_count_display', 'application_count_display', 'milestone_progress_display',
        'created_at', 'updated_at'
    ]
    
    inlines = [CollaborationParticipationInline, CollaborationMilestoneInline]
    
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'collaboration_type', 'initiator_club', 'created_by')
        }),
        ('Description', {
            'fields': ('short_description', 'description', 'tags')
        }),
        ('Leadership', {
            'fields': ('project_lead',)
        }),
        ('Timeline', {
            'fields': ('start_date', 'end_date', 'application_deadline')
        }),
        ('Participation', {
            'fields': ('max_participants', 'min_participants', 'allows_external_participants')
        }),
        ('Project Details', {
            'fields': ('objectives', 'deliverables', 'requirements', 'skills_needed'),
            'classes': ('collapse',)
        }),
        ('Resources', {
            'fields': ('budget', 'resources_needed', 'resources_provided'),
            'classes': ('collapse',)
        }),
        ('Settings', {
            'fields': ('status', 'priority', 'privacy', 'progress_percentage')
        }),
        ('Communication', {
            'fields': ('communication_channels', 'meeting_schedule'),
            'classes': ('collapse',)
        }),
        ('Media', {
            'fields': ('featured_image', 'documents'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': (
                'total_participants', 'total_applications', 'success_rating',
                'participant_count_display', 'application_count_display', 
                'milestone_progress_display'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_collaborations', 'mark_in_progress', 'mark_completed']
    
    def participant_count_display(self, obj):
        count = obj.total_participants
        if count > 0:
            url = reverse('admin:collaboration_collaborationparticipation_changelist') + f'?collaboration__id__exact={obj.id}'
            return format_html('<a href="{}">{}</a>', url, count)
        return count
    participant_count_display.short_description = 'Participants'
    
    def application_count_display(self, obj):
        count = obj.total_applications
        if count > 0:
            url = reverse('admin:collaboration_collaborationparticipation_changelist') + f'?collaboration__id__exact={obj.id}&status__exact=pending'
            return format_html('<a href="{}">{} ({} pending)</a>', url, count, 
                             obj.participations.filter(status='pending').count())
        return count
    application_count_display.short_description = 'Applications'
    
    def milestone_progress_display(self, obj):
        total = obj.milestone_objects.count()
        completed = obj.milestone_objects.filter(status='completed').count()
        if total > 0:
            percentage = int((completed / total) * 100)
            return format_html('{}/{} ({}%)', completed, total, percentage)
        return "No milestones"
    milestone_progress_display.short_description = 'Milestone Progress'
    
    def approve_collaborations(self, request, queryset):
        """Bulk approve collaborations"""
        updated = queryset.filter(status='draft').update(status='open')
        self.message_user(request, f'{updated} collaborations approved and opened for applications.')
    approve_collaborations.short_description = "Approve and open for applications"
    
    def mark_in_progress(self, request, queryset):
        """Mark collaborations as in progress"""
        updated = queryset.filter(status='open').update(status='in_progress')
        self.message_user(request, f'{updated} collaborations marked as in progress.')
    mark_in_progress.short_description = "Mark as in progress"
    
    def mark_completed(self, request, queryset):
        """Mark collaborations as completed"""
        updated = queryset.filter(status='in_progress').update(status='completed', progress_percentage=100)
        self.message_user(request, f'{updated} collaborations marked as completed.')
    mark_completed.short_description = "Mark as completed"
    
    def get_queryset(self, request):
        """Filter based on user permissions"""
        qs = super().get_queryset(request).select_related(
            'collaboration_type', 'initiator_club', 'created_by', 'project_lead'
        )
        
        if request.user.is_superuser:
            return qs
        
        # College admins see only their college collaborations
        if hasattr(request.user, 'user_type') and request.user.user_type == 'college_admin':
            return qs.filter(initiator_club__college__domain=request.user.college_email_domain)
        
        return qs


@admin.register(CollaborationParticipation)
class CollaborationParticipationAdmin(admin.ModelAdmin):
    """Collaboration Participation admin"""
    
    list_display = [
        'collaboration', 'club', 'status', 'role', 'committed_members',
        'contribution_score', 'primary_contact', 'created_at'
    ]
    
    list_filter = [
        'status', 'role', 'collaboration__collaboration_type',
        'joined_at', 'created_at'
    ]
    
    search_fields = [
        'collaboration__title', 'club__name', 'primary_contact__full_name',
        'application_message'
    ]
    
    readonly_fields = [
        'id', 'joined_at', 'approved_by', 'tasks_completed',
        'milestones_achieved', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        (None, {
            'fields': ('collaboration', 'club', 'status', 'role')
        }),
        ('Application', {
            'fields': ('application_message', 'committed_members', 
                      'committed_hours_per_week', 'committed_resources')
        }),
        ('Contact', {
            'fields': ('primary_contact',)
        }),
        ('Approval', {
            'fields': ('joined_at', 'approved_by'),
            'classes': ('collapse',)
        }),
        ('Performance', {
            'fields': ('contribution_score', 'tasks_completed', 'milestones_achieved'),
            'classes': ('collapse',)
        }),
        ('Feedback', {
            'fields': ('final_rating', 'feedback'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_participations', 'reject_participations']
    
    def approve_participations(self, request, queryset):
        """Bulk approve participations"""
        approved_count = 0
        for participation in queryset.filter(status='pending'):
            if participation.approve_participation(request.user):
                approved_count += 1
        
        self.message_user(request, f'{approved_count} participations approved successfully.')
    approve_participations.short_description = "Approve selected participations"
    
    def reject_participations(self, request, queryset):
        """Bulk reject participations"""
        rejected_count = 0
        for participation in queryset.filter(status='pending'):
            if participation.reject_participation("Rejected by admin"):
                rejected_count += 1
        
        self.message_user(request, f'{rejected_count} participations rejected.')
    reject_participations.short_description = "Reject selected participations"
    
    def get_queryset(self, request):
        """Filter based on user permissions"""
        qs = super().get_queryset(request).select_related(
            'collaboration', 'club', 'primary_contact', 'approved_by'
        )
        
        if request.user.is_superuser:
            return qs
        
        if hasattr(request.user, 'user_type') and request.user.user_type == 'college_admin':
            return qs.filter(collaboration__initiator_club__college__domain=request.user.college_email_domain)
        
        return qs


@admin.register(CollaborationMilestone)
class CollaborationMilestoneAdmin(admin.ModelAdmin):
    """Collaboration Milestone admin"""
    
    list_display = [
        'title', 'collaboration', 'due_date', 'status', 'progress_percentage',
        'assigned_by', 'is_overdue_display'
    ]
    
    list_filter = ['status', 'due_date', 'created_at']
    search_fields = ['title', 'description', 'collaboration__title']
    
    readonly_fields = [
        'id', 'completed_at', 'completed_by', 'is_overdue_display',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        (None, {
            'fields': ('collaboration', 'title', 'description', 'due_date')
        }),
        ('Assignment', {
            'fields': ('assigned_clubs', 'assigned_by')
        }),
        ('Progress', {
            'fields': ('status', 'progress_percentage')
        }),
        ('Completion', {
            'fields': ('completed_at', 'completed_by'),
            'classes': ('collapse',)
        }),
        ('Deliverables', {
            'fields': ('deliverables', 'attachments'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_overdue_display(self, obj):
        if obj.is_overdue:
            return format_html('<span style="color: red;">Yes</span>')
        return 'No'
    is_overdue_display.short_description = 'Overdue'


@admin.register(CollaborationMessage)
class CollaborationMessageAdmin(admin.ModelAdmin):
    """Collaboration Message admin"""
    
    list_display = [
        'collaboration', 'sender', 'message_type', 'subject_display',
        'is_announcement', 'is_pinned', 'created_at'
    ]
    
    list_filter = [
        'message_type', 'is_announcement', 'is_pinned', 'created_at'
    ]
    
    search_fields = ['collaboration__title', 'sender__full_name', 'subject', 'content']
    
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('collaboration', 'sender', 'message_type')
        }),
        ('Content', {
            'fields': ('subject', 'content', 'attachments')
        }),
        ('Threading', {
            'fields': ('parent_message',),
            'classes': ('collapse',)
        }),
        ('Settings', {
            'fields': ('is_announcement', 'is_pinned')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def subject_display(self, obj):
        return obj.subject[:50] + "..." if len(obj.subject) > 50 else obj.subject
    subject_display.short_description = 'Subject'


@admin.register(CollaborationResource)
class CollaborationResourceAdmin(admin.ModelAdmin):
    """Collaboration Resource admin"""
    
    list_display = [
        'title', 'collaboration', 'resource_type', 'is_public',
        'uploaded_by', 'download_count', 'created_at'
    ]
    
    list_filter = ['resource_type', 'is_public', 'created_at']
    search_fields = ['title', 'description', 'collaboration__title']
    
    readonly_fields = ['id', 'download_count', 'file_size_display', 'created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('collaboration', 'title', 'description', 'resource_type')
        }),
        ('File/Link', {
            'fields': ('file', 'external_url', 'file_size_display')
        }),
        ('Access Control', {
            'fields': ('is_public', 'allowed_clubs')
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
