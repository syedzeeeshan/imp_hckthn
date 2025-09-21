"""
Club models for Campus Club Management Suite
Core models for club management, membership, and categories
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid

class ClubCategory(models.Model):
    """Categories for organizing clubs"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Icon class name")
    color = models.CharField(max_length=7, default="#007bff", help_text="Hex color code")
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'club_categories'
        verbose_name = 'Club Category'
        verbose_name_plural = 'Club Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def total_clubs(self):
        """Get total number of clubs in this category"""
        return self.clubs.filter(is_active=True).count()


class Club(models.Model):
    """Main Club model"""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending Approval'),
        ('suspended', 'Suspended'),
    ]
    
    PRIVACY_CHOICES = [
        ('public', 'Public'),
        ('private', 'Private'),
        ('college_only', 'College Only'),
    ]
    
    # Primary Fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField()
    short_description = models.CharField(max_length=300, blank=True)
    
    # Visual Assets
    logo = models.ImageField(upload_to='club_logos/', blank=True, null=True)
    cover_image = models.ImageField(upload_to='club_covers/', blank=True, null=True)
    
    # Organization
    category = models.ForeignKey(ClubCategory, on_delete=models.SET_NULL, null=True, related_name='clubs')
    college = models.ForeignKey('authentication.College', on_delete=models.CASCADE, related_name='clubs')
    
    # Contact Information
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=15, blank=True)
    website = models.URLField(blank=True)
    social_links = models.JSONField(default=dict, blank=True, help_text="Social media links")
    
    # Meeting Information
    meeting_location = models.CharField(max_length=200, blank=True)
    meeting_schedule = models.CharField(max_length=200, blank=True)
    meeting_days = models.JSONField(default=list, blank=True, help_text="Days of the week")
    
    # Status and Settings
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    privacy = models.CharField(max_length=20, choices=PRIVACY_CHOICES, default='public')
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    requires_approval = models.BooleanField(default=False)
    
    # Membership Limits
    max_members = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    
    # Financial Information
    membership_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Activity Stats (calculated fields)
    total_events = models.IntegerField(default=0)
    total_collaborations = models.IntegerField(default=0)
    
    # Management
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_clubs')
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='ClubMembership',
        related_name='joined_clubs',
        through_fields=('club', 'user')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'clubs'
        verbose_name = 'Club'
        verbose_name_plural = 'Clubs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'is_active']),
            models.Index(fields=['college', 'category']),
            models.Index(fields=['slug']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            
            while Club.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            self.slug = slug
        
        super().save(*args, **kwargs)
    
    @property
    def member_count(self):
        """Get total number of members"""
        return self.memberships.filter(status='active').count()
    
    @property
    def leader_count(self):
        """Get total number of leaders"""
        return self.memberships.filter(status='active', role='leader').count()
    
    @property
    def pending_requests(self):
        """Get number of pending membership requests"""
        return self.memberships.filter(status='pending').count()
    
    @property
    def is_full(self):
        """Check if club is at maximum capacity"""
        if not self.max_members:
            return False
        return self.member_count >= self.max_members
    
    @property
    def activity_score(self):
        """Calculate club activity score"""
        base_score = 0
        base_score += self.total_events * 5
        base_score += self.member_count * 2
        base_score += self.total_collaborations * 10
        
        # Recent activity bonus
        recent_events = self.events.filter(
            created_at__gte=timezone.now() - timezone.timedelta(days=30)
        ).count()
        base_score += recent_events * 3
        
        return min(base_score, 1000)  # Cap at 1000
    
    def get_social_links(self):
        """Get formatted social media links"""
        default_links = {
            'facebook': '',
            'twitter': '',
            'instagram': '',
            'linkedin': '',
            'discord': '',
            'telegram': ''
        }
        default_links.update(self.social_links or {})
        return default_links
    
    def can_user_join(self, user):
        """Check if user can join this club"""
        if not user.is_authenticated:
            return False
        
        if self.is_full:
            return False
        
        if self.memberships.filter(user=user, status__in=['active', 'pending']).exists():
            return False
        
        if self.privacy == 'college_only' and user.college_email_domain != self.college.domain:
            return False
        
        return True


class ClubMembership(models.Model):
    """Club membership model with roles and status"""
    
    ROLE_CHOICES = [
        ('member', 'Member'),
        ('leader', 'Leader'),
        ('admin', 'Admin'),
        ('treasurer', 'Treasurer'),
        ('secretary', 'Secretary'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('pending', 'Pending'),
        ('inactive', 'Inactive'),
        ('banned', 'Banned'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='memberships')
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Additional Information
    joined_at = models.DateTimeField(null=True, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_memberships')
    
    # Activity Tracking
    events_attended = models.IntegerField(default=0)
    last_activity = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'club_memberships'
        verbose_name = 'Club Membership'
        verbose_name_plural = 'Club Memberships'
        unique_together = ['user', 'club']
        indexes = [
            models.Index(fields=['club', 'status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['role']),
        ]
    
    def __str__(self):
        return f"{self.user.full_name} - {self.club.name} ({self.role})"
    
    def approve_membership(self, approved_by_user):
        """Approve pending membership"""
        if self.status == 'pending':
            self.status = 'active'
            self.joined_at = timezone.now()
            self.approved_by = approved_by_user
            self.save()
            return True
        return False
    
    def reject_membership(self):
        """Reject pending membership"""
        if self.status == 'pending':
            self.delete()
            return True
        return False
    
    @property
    def is_leader(self):
        """Check if member has leadership role"""
        return self.role in ['leader', 'admin']
    
    @property
    def membership_duration(self):
        """Get membership duration"""
        if self.joined_at:
            return timezone.now() - self.joined_at
        return None


class ClubSettings(models.Model):
    """Club-specific settings and preferences"""
    
    club = models.OneToOneField(Club, on_delete=models.CASCADE, related_name='settings')
    
    # Notification Settings
    notify_new_members = models.BooleanField(default=True)
    notify_events = models.BooleanField(default=True)
    notify_collaborations = models.BooleanField(default=True)
    
    # Privacy Settings
    show_member_list = models.BooleanField(default=True)
    show_contact_info = models.BooleanField(default=True)
    allow_member_invites = models.BooleanField(default=True)
    
    # Event Settings
    auto_approve_events = models.BooleanField(default=False)
    require_event_approval = models.BooleanField(default=True)
    
    # Custom Fields
    custom_fields = models.JSONField(default=dict, blank=True)
    
    # Integration Settings
    calendar_sync = models.BooleanField(default=False)
    email_integration = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'club_settings'
        verbose_name = 'Club Settings'
        verbose_name_plural = 'Club Settings'
    
    def __str__(self):
        return f"{self.club.name} Settings"


class ClubAnnouncement(models.Model):
    """Club announcements and news"""
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='announcements')
    title = models.CharField(max_length=200)
    content = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    
    # Target Audience
    target_all_members = models.BooleanField(default=True)
    target_roles = models.JSONField(default=list, blank=True, help_text="Specific roles to target")
    
    # Settings
    is_published = models.BooleanField(default=True)
    send_email = models.BooleanField(default=False)
    send_notification = models.BooleanField(default=True)
    
    # Scheduling
    publish_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    views = models.IntegerField(default=0)
    
    # Management
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'club_announcements'
        verbose_name = 'Club Announcement'
        verbose_name_plural = 'Club Announcements'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['club', 'is_published']),
            models.Index(fields=['priority']),
            models.Index(fields=['publish_at']),
        ]
    
    def __str__(self):
        return f"{self.club.name} - {self.title}"
    
    @property
    def is_active(self):
        """Check if announcement is currently active"""
        now = timezone.now()
        
        if not self.is_published:
            return False
        
        if self.publish_at and self.publish_at > now:
            return False
        
        if self.expires_at and self.expires_at < now:
            return False
        
        return True
    
    def increment_views(self):
        """Increment view count"""
        self.views += 1
        self.save(update_fields=['views'])


# Signal handlers for club models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=Club)
def create_club_settings(sender, instance, created, **kwargs):
    """Create club settings when club is created"""
    if created:
        ClubSettings.objects.get_or_create(club=instance)

@receiver(post_save, sender=ClubMembership)
def update_club_stats(sender, instance, **kwargs):
    """Update club statistics when membership changes"""
    if instance.status == 'active':
        # Update user profile stats
        if hasattr(instance.user, 'profile'):
            profile = instance.user.profile
            profile.total_clubs_joined = ClubMembership.objects.filter(
                user=instance.user, 
                status='active'
            ).count()
            profile.save()

@receiver(post_delete, sender=Club)
def cleanup_club_files(sender, instance, **kwargs):
    """Clean up club files when club is deleted"""
    if instance.logo:
        try:
            instance.logo.delete(save=False)
        except Exception:
            pass
    
    if instance.cover_image:
        try:
            instance.cover_image.delete(save=False)
        except Exception:
            pass
