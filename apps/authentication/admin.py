"""
Django admin configuration for authentication app
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from .models import User, College, UserProfile

@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
    """College admin configuration"""
    
    list_display = [
        'name', 'domain', 'location', 'is_verified', 'created_at'
    ]
    
    list_filter = ['is_verified', 'created_at']
    search_fields = ['name', 'domain', 'location']
    
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'domain', 'location', 'website')
        }),
        ('Status', {
            'fields': ('is_verified',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('users')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User admin configuration"""
    
    list_display = [
        'email', 'full_name', 'user_type', 'is_verified', 
        'is_college_verified', 'is_active', 'created_at'
    ]
    
    list_filter = [
        'user_type', 'is_verified', 'is_college_verified', 
        'is_active', 'is_staff', 'created_at'
    ]
    
    search_fields = ['email', 'full_name', 'college_name', 'student_id']
    
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'last_activity', 
        'login_count', 'email_verification_sent_at'
    ]
    
    fieldsets = (
        (None, {
            'fields': ('email', 'password')
        }),
        ('Personal info', {
            'fields': ('full_name', 'phone_number', 'avatar', 'bio', 'date_of_birth')
        }),
        ('User Type & Status', {
            'fields': ('user_type', 'is_verified', 'is_college_verified', 'is_profile_complete')
        }),
        ('College Information', {
            'fields': ('college', 'college_name', 'student_id', 'graduation_year'),
            'classes': ('collapse',)
        }),
        ('Email Verification', {
            'fields': ('is_email_verified', 'email_verification_token', 'email_verification_sent_at'),
            'classes': ('collapse',)
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Settings', {
            'fields': ('timezone', 'language'),
            'classes': ('collapse',)
        }),
        ('Activity', {
            'fields': ('last_login', 'last_activity', 'login_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'password1', 'password2', 'user_type'),
        }),
    )
    
    ordering = ['-created_at']
    
    actions = ['verify_users', 'unverify_users', 'verify_college', 'unverify_college']
    
    def verify_users(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} users verified.')
    verify_users.short_description = "Verify selected users"
    
    def unverify_users(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f'{updated} users unverified.')
    unverify_users.short_description = "Unverify selected users"
    
    def verify_college(self, request, queryset):
        updated = queryset.update(is_college_verified=True)
        self.message_user(request, f'{updated} users college-verified.')
    verify_college.short_description = "Verify college for selected users"
    
    def unverify_college(self, request, queryset):
        updated = queryset.update(is_college_verified=False)
        self.message_user(request, f'{updated} users college-unverified.')
    unverify_college.short_description = "Unverify college for selected users"


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """User Profile admin configuration"""
    
    list_display = [
        'user', 'profile_visibility', 'major', 'academic_year', 'created_at'
    ]
    
    list_filter = ['profile_visibility', 'show_email', 'show_phone', 'created_at']
    search_fields = ['user__full_name', 'user__email', 'major', 'department']
    
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('user',)
        }),
        ('Social Links', {
            'fields': ('linkedin_url', 'github_url', 'twitter_url', 'personal_website'),
            'classes': ('collapse',)
        }),
        ('Academic Information', {
            'fields': ('major', 'department', 'academic_year', 'gpa')
        }),
        ('Interests & Skills', {
            'fields': ('interests', 'skills')
        }),
        ('Privacy Settings', {
            'fields': ('profile_visibility', 'show_email', 'show_phone')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


# Unregister default User admin if it exists
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
