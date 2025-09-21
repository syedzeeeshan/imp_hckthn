"""
Collaboration models for Campus Club Management Suite
Inter-college partnerships, joint projects, and collaboration management
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid

class CollaborationType(models.Model):
    """Types of collaboration available"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=7, default="#007bff")
    is_active = models.BooleanField(default=True)
    
    # Requirements
    min_participants = models.IntegerField(default=2, validators=[MinValueValidator(2)])
    max_participants = models.IntegerField(default=10, validators=[MinValueValidator(2)])
    requires_approval = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'collaboration_types'
        verbose_name = 'Collaboration Type'
        verbose_name_plural = 'Collaboration Types'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def total_collaborations(self):
        return self.collaborations.filter(is_active=True).count()


class Collaboration(models.Model):
    """Main collaboration model for inter-college projects"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('open', 'Open for Applications'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('on_hold', 'On Hold'),
    ]
    
    PRIVACY_CHOICES = [
        ('public', 'Public'),
        ('college_network', 'College Network Only'),
        ('invite_only', 'Invite Only'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    # Primary Fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField()
    short_description = models.CharField(max_length=300, blank=True)
    
    # Classification
    collaboration_type = models.ForeignKey(CollaborationType, on_delete=models.SET_NULL, null=True, related_name='collaborations')
    tags = models.JSONField(default=list, blank=True, help_text="Project tags for search and categorization")
    
    # Leadership & Ownership
    initiator_club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='initiated_collaborations')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_collaborations')
    project_lead = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='led_collaborations')
    
    # Timeline
    start_date = models.DateField()
    end_date = models.DateField()
    application_deadline = models.DateTimeField(null=True, blank=True)
    
    # Participation
    max_participants = models.IntegerField(validators=[MinValueValidator(2)])
    min_participants = models.IntegerField(default=2, validators=[MinValueValidator(2)])
    participating_clubs = models.ManyToManyField('clubs.Club', through='CollaborationParticipation', related_name='collaborations')
    
    # Project Details
    objectives = models.JSONField(default=list, blank=True, help_text="List of project objectives")
    deliverables = models.JSONField(default=list, blank=True, help_text="Expected deliverables")
    requirements = models.JSONField(default=list, blank=True, help_text="Requirements for participation")
    skills_needed = models.JSONField(default=list, blank=True, help_text="Skills needed for the project")
    
    # Resources
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    resources_needed = models.JSONField(default=list, blank=True)
    resources_provided = models.JSONField(default=list, blank=True)
    
    # Settings
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    privacy = models.CharField(max_length=20, choices=PRIVACY_CHOICES, default='public')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    is_active = models.BooleanField(default=True)
    allows_external_participants = models.BooleanField(default=False)
    
    # Progress Tracking
    progress_percentage = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    milestones = models.JSONField(default=list, blank=True)
    
    # Communication
    communication_channels = models.JSONField(default=dict, blank=True)
    meeting_schedule = models.CharField(max_length=200, blank=True)
    
    # Media
    featured_image = models.ImageField(upload_to='collaboration_images/', blank=True, null=True)
    documents = models.JSONField(default=list, blank=True)
    
    # Analytics
    total_applications = models.IntegerField(default=0)
    total_participants = models.IntegerField(default=0)
    success_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'collaborations'
        verbose_name = 'Collaboration'
        verbose_name_plural = 'Collaborations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'is_active']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['slug']),
            models.Index(fields=['privacy']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            import random
            import string
            
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            
            while Collaboration.objects.filter(slug=slug).exists():
                random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
                slug = f"{base_slug}-{random_suffix}"
                counter += 1
                if counter > 100:
                    break
            
            self.slug = slug
        
        super().save(*args, **kwargs)
    
    @property
    def is_open_for_applications(self):
        """Check if collaboration is accepting applications"""
        now = timezone.now()
        return (
            self.status == 'open' and
            self.is_active and
            (not self.application_deadline or self.application_deadline > now) and
            self.total_participants < self.max_participants
        )
    
    @property
    def is_full(self):
        """Check if collaboration has reached max participants"""
        return self.total_participants >= self.max_participants
    
    @property
    def available_spots(self):
        """Get number of available spots"""
        return max(0, self.max_participants - self.total_participants)
    
    @property
    def duration_days(self):
        """Get project duration in days"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return 0
    
    @property
    def is_upcoming(self):
        """Check if collaboration is upcoming"""
        return self.start_date > timezone.now().date()
    
    @property
    def is_ongoing(self):
        """Check if collaboration is currently active"""
        now = timezone.now().date()
        return self.start_date <= now <= self.end_date
    
    @property
    def is_past(self):
        """Check if collaboration has ended"""
        return self.end_date < timezone.now().date()
    
    def can_club_apply(self, club):
        """Check if a club can apply to join this collaboration"""
        if not self.is_open_for_applications:
            return False
        
        if self.participating_clubs.filter(id=club.id).exists():
            return False
        
        if self.privacy == 'college_network':
            # Check if club is in the same network/region
            return club.college.domain == self.initiator_club.college.domain
        elif self.privacy == 'invite_only':
            return False
        
        return True
    
    def get_participation_status(self, club):
        """Get club's participation status"""
        try:
            participation = self.participations.get(club=club)
            return participation.status
        except CollaborationParticipation.DoesNotExist:
            return None


class CollaborationParticipation(models.Model):
    """Club participation in collaborations"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('active', 'Active Participant'),
        ('withdrawn', 'Withdrawn'),
        ('completed', 'Completed'),
    ]
    
    ROLE_CHOICES = [
        ('participant', 'Participant'),
        ('co_lead', 'Co-Lead'),
        ('contributor', 'Contributor'),
        ('advisor', 'Advisor'),
        ('sponsor', 'Sponsor'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    collaboration = models.ForeignKey(Collaboration, on_delete=models.CASCADE, related_name='participations')
    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='collaboration_participations')
    
    # Application Details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='participant')
    application_message = models.TextField(blank=True)
    
    # Commitment
    committed_members = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    committed_hours_per_week = models.IntegerField(default=5, validators=[MinValueValidator(1)])
    committed_resources = models.JSONField(default=list, blank=True)
    
    # Contact
    primary_contact = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='collaboration_contacts')
    
    # Timeline
    joined_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_participations')
    
    # Performance Tracking
    contribution_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    tasks_completed = models.IntegerField(default=0)
    milestones_achieved = models.IntegerField(default=0)
    
    # Feedback
    final_rating = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    feedback = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'collaboration_participations'
        verbose_name = 'Collaboration Participation'
        verbose_name_plural = 'Collaboration Participations'
        unique_together = ['collaboration', 'club']
        indexes = [
            models.Index(fields=['collaboration', 'status']),
            models.Index(fields=['club', 'status']),
        ]
    
    def __str__(self):
        return f"{self.club.name} in {self.collaboration.title}"
    
    def approve_participation(self, approved_by_user):
        """Approve club participation"""
        if self.status == 'pending':
            self.status = 'approved'
            self.joined_at = timezone.now()
            self.approved_by = approved_by_user
            self.save()
            
            # Update collaboration participant count
            self.collaboration.total_participants = self.collaboration.participations.filter(
                status__in=['approved', 'active', 'completed']
            ).count()
            self.collaboration.save(update_fields=['total_participants'])
            
            return True
        return False
    
    def reject_participation(self, reason=""):
        """Reject club participation"""
        if self.status == 'pending':
            self.status = 'rejected'
            self.feedback = reason
            self.save()
            return True
        return False
    
    def withdraw_participation(self):
        """Withdraw from collaboration"""
        if self.status in ['approved', 'active']:
            self.status = 'withdrawn'
            self.save()
            
            # Update collaboration participant count
            self.collaboration.total_participants = self.collaboration.participations.filter(
                status__in=['approved', 'active', 'completed']
            ).count()
            self.collaboration.save(update_fields=['total_participants'])
            
            return True
        return False


class CollaborationMilestone(models.Model):
    """Project milestones and deliverables"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    collaboration = models.ForeignKey(Collaboration, on_delete=models.CASCADE, related_name='milestone_objects')
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date = models.DateField()
    
    # Assignment
    assigned_clubs = models.ManyToManyField('clubs.Club', blank=True, related_name='assigned_milestones')
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    # Progress
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress_percentage = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Completion
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='completed_milestones')
    
    # Deliverables
    deliverables = models.JSONField(default=list, blank=True)
    attachments = models.JSONField(default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'collaboration_milestones'
        verbose_name = 'Collaboration Milestone'
        verbose_name_plural = 'Collaboration Milestones'
        ordering = ['due_date']
    
    def __str__(self):
        return f"{self.collaboration.title} - {self.title}"
    
    @property
    def is_overdue(self):
        """Check if milestone is overdue"""
        return (
            self.status not in ['completed', 'cancelled'] and
            self.due_date < timezone.now().date()
        )
    
    def mark_completed(self, completed_by_user):
        """Mark milestone as completed"""
        if self.status != 'completed':
            self.status = 'completed'
            self.progress_percentage = 100
            self.completed_at = timezone.now()
            self.completed_by = completed_by_user
            self.save()
            
            # Update collaboration progress
            self._update_collaboration_progress()
            return True
        return False
    
    def _update_collaboration_progress(self):
        """Update overall collaboration progress"""
        total_milestones = self.collaboration.milestone_objects.count()
        completed_milestones = self.collaboration.milestone_objects.filter(status='completed').count()
        
        if total_milestones > 0:
            progress = int((completed_milestones / total_milestones) * 100)
            self.collaboration.progress_percentage = progress
            self.collaboration.save(update_fields=['progress_percentage'])


class CollaborationMessage(models.Model):
    """Communication within collaborations"""
    
    MESSAGE_TYPES = [
        ('general', 'General Discussion'),
        ('announcement', 'Announcement'),
        ('milestone_update', 'Milestone Update'),
        ('question', 'Question'),
        ('resource_share', 'Resource Sharing'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    collaboration = models.ForeignKey(Collaboration, on_delete=models.CASCADE, related_name='messages')
    
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_collaboration_messages')
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='general')
    
    subject = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    attachments = models.JSONField(default=list, blank=True)
    
    # Threading
    parent_message = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    
    # Status
    is_announcement = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'collaboration_messages'
        verbose_name = 'Collaboration Message'
        verbose_name_plural = 'Collaboration Messages'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.collaboration.title} - {self.sender.full_name}"


class CollaborationResource(models.Model):
    """Shared resources within collaborations"""
    
    RESOURCE_TYPES = [
        ('document', 'Document'),
        ('template', 'Template'),
        ('dataset', 'Dataset'),
        ('tool', 'Tool/Software'),
        ('link', 'External Link'),
        ('media', 'Media File'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    collaboration = models.ForeignKey(Collaboration, on_delete=models.CASCADE, related_name='shared_resources')
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES, default='document')
    
    # File or Link
    file = models.FileField(upload_to='collaboration_resources/', blank=True, null=True)
    external_url = models.URLField(blank=True)
    
    # Access Control
    is_public = models.BooleanField(default=False)
    allowed_clubs = models.ManyToManyField('clubs.Club', blank=True, related_name='accessible_collaboration_resources')
    
    # Metadata
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    download_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'collaboration_resources'
        verbose_name = 'Collaboration Resource'
        verbose_name_plural = 'Collaboration Resources'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.collaboration.title} - {self.title}"
    
    def can_user_access(self, user):
        """Check if user can access this resource"""
        if self.is_public:
            return True
        
        if not user.is_authenticated:
            return False
        
        # Check if user's club is participating
        user_clubs = user.joined_clubs.filter(
            collaboration_participations__collaboration=self.collaboration,
            collaboration_participations__status__in=['approved', 'active', 'completed']
        )
        
        if self.allowed_clubs.exists():
            return self.allowed_clubs.filter(id__in=user_clubs.values_list('id', flat=True)).exists()
        else:
            return user_clubs.exists()


# # Signal handlers
# from django.db.models.signals import post_save, post_delete
# from django.dispatch import receiver

# @receiver(post_save, sender=CollaborationParticipation)
# def update_collaboration_stats(sender, instance, **kwargs):
#     """Update collaboration statistics"""
#     collaboration = instance.collaboration
#     collaboration.total_participants = collaboration.participations.filter(
#         status__in=['approved', 'active', 'completed']
#     ).count()
#     collaboration.total_applications = collaboration.participations.count()
#     collaboration.save(update_fields=['total_participants', 'total_applications'])

# @receiver(post_save, sender=Collaboration)
# def update_club_collaboration_count(sender, instance, created, **kwargs):
#     """Update club's collaboration count"""
#     if created:
#         club = instance.initiator_club
#         if hasattr(club, 'total_collaborations'):
#             club.total_collaborations += 1
#             club.save(update_fields=['total_collaborations'])

# @receiver(post_delete, sender=Collaboration)
# def cleanup_collaboration_files(sender, instance, **kwargs):
#     """Clean up collaboration files when deleted"""
#     if instance.featured_image:
#         try:
#             instance.featured_image.delete(save=False)
#         except Exception:
#             pass
