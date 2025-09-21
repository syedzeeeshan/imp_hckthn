"""
Event models for Campus Club Management Suite
Comprehensive event management with RSVP, QR codes, and analytics
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid
import qrcode
from io import BytesIO
from django.core.files import File

class EventCategory(models.Model):
    """Categories for organizing events"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=7, default="#007bff")
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'event_categories'
        verbose_name = 'Event Category'
        verbose_name_plural = 'Event Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def total_events(self):
        return self.events.filter(is_active=True).count()


class Event(models.Model):
    """Main Event model"""
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PRIVACY_CHOICES = [
        ('public', 'Public'),
        ('private', 'Private'),
        ('club_only', 'Club Members Only'),
        ('college_only', 'College Only'),
    ]
    
    TYPE_CHOICES = [
        ('meeting', 'Meeting'),
        ('workshop', 'Workshop'),
        ('seminar', 'Seminar'),
        ('competition', 'Competition'),
        ('social', 'Social Event'),
        ('fundraiser', 'Fundraiser'),
        ('conference', 'Conference'),
        ('other', 'Other'),
    ]
    
    # Primary Fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField()
    short_description = models.CharField(max_length=300, blank=True)
    
    # Event Details
    event_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='other')
    category = models.ForeignKey(EventCategory, on_delete=models.SET_NULL, null=True, related_name='events')
    
    # Organization
    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='events')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_events')
    
    # Date and Time
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    registration_deadline = models.DateTimeField(null=True, blank=True)
    
    # Location
    location = models.CharField(max_length=300)
    venue_details = models.TextField(blank=True)
    is_online = models.BooleanField(default=False)
    meeting_link = models.URLField(blank=True)
    
    # Visual Assets
    featured_image = models.ImageField(upload_to='event_images/', blank=True, null=True)
    qr_code = models.ImageField(upload_to='event_qr_codes/', blank=True, null=True)
    
    # Capacity and Registration
    max_attendees = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    registration_required = models.BooleanField(default=True)
    registration_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Status and Settings
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    privacy = models.CharField(max_length=20, choices=PRIVACY_CHOICES, default='public')
    is_active = models.BooleanField(default=True)
    requires_approval = models.BooleanField(default=False)
    
    # Additional Information
    agenda = models.JSONField(default=list, blank=True)
    speakers = models.JSONField(default=list, blank=True)
    sponsors = models.JSONField(default=list, blank=True)
    tags = models.JSONField(default=list, blank=True)
    
    # Resources
    resources = models.JSONField(default=list, blank=True)
    external_links = models.JSONField(default=list, blank=True)
    
    # Analytics Fields (calculated)
    total_registrations = models.IntegerField(default=0)
    total_attendees = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'events'
        verbose_name = 'Event'
        verbose_name_plural = 'Events'
        ordering = ['-start_datetime']
        indexes = [
            models.Index(fields=['status', 'is_active']),
            models.Index(fields=['club', 'start_datetime']),
            models.Index(fields=['slug']),
            models.Index(fields=['start_datetime', 'end_datetime']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        # Generate slug
        if not self.slug:
            from django.utils.text import slugify
            import random
            import string
            
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            
            while Event.objects.filter(slug=slug).exists():
                random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
                slug = f"{base_slug}-{random_suffix}"
                counter += 1
                if counter > 100:  # Prevent infinite loop
                    break
            
            self.slug = slug
        
        super().save(*args, **kwargs)
        
        # Generate QR code after saving
        if not self.qr_code:
            self.generate_qr_code()
    
    def generate_qr_code(self):
        """Generate QR code for event check-in"""
        try:
            qr_data = f"event:{self.id}:{self.slug}"
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(qr_data)
            qr.make(fit=True)
            
            qr_image = qr.make_image(fill_color="black", back_color="white")
            
            # Save to BytesIO
            buffer = BytesIO()
            qr_image.save(buffer, format='PNG')
            buffer.seek(0)
            
            # Save to model field
            filename = f'event_qr_{self.slug}.png'
            self.qr_code.save(filename, File(buffer), save=False)
            self.save(update_fields=['qr_code'])
        except Exception as e:
            print(f"Failed to generate QR code for event {self.id}: {e}")
    
    @property
    def is_upcoming(self):
        """Check if event is upcoming"""
        return self.start_datetime > timezone.now()
    
    @property
    def is_ongoing(self):
        """Check if event is currently ongoing"""
        now = timezone.now()
        return self.start_datetime <= now <= self.end_datetime
    
    @property
    def is_past(self):
        """Check if event is past"""
        return self.end_datetime < timezone.now()
    
    @property
    def is_full(self):
        """Check if event is at capacity"""
        if not self.max_attendees:
            return False
        return self.total_registrations >= self.max_attendees
    
    @property
    def available_spots(self):
        """Get number of available spots"""
        if not self.max_attendees:
            return None
        return max(0, self.max_attendees - self.total_registrations)
    
    @property
    def registration_open(self):
        """Check if registration is still open"""
        now = timezone.now()
        
        if self.registration_deadline and now > self.registration_deadline:
            return False
        
        if self.is_full:
            return False
        
        if self.status != 'published':
            return False
        
        return True
    
    @property
    def duration_hours(self):
        """Get event duration in hours"""
        duration = self.end_datetime - self.start_datetime
        return duration.total_seconds() / 3600
    
    @property
    def attendance_rate(self):
        """Calculate attendance rate percentage"""
        if self.total_registrations == 0:
            return 0
        return round((self.total_attendees / self.total_registrations) * 100, 2)
    
    def can_user_register(self, user):
        """Check if user can register for this event"""
        if not user.is_authenticated:
            return False
        
        if not self.registration_open:
            return False
        
        if EventRegistration.objects.filter(user=user, event=self, status__in=['registered', 'attended']).exists():
            return False
        
        # Check privacy restrictions
        if self.privacy == 'club_only':
            return self.club.memberships.filter(user=user, status='active').exists()
        elif self.privacy == 'college_only':
            return user.college_email_domain == self.club.college.domain
        
        return True


class EventRegistration(models.Model):
    """Event registration model"""
    
    STATUS_CHOICES = [
        ('registered', 'Registered'),
        ('waitlisted', 'Waitlisted'),
        ('attended', 'Attended'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='event_registrations')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='registrations')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='registered')
    
    # Registration Details
    registration_data = models.JSONField(default=dict, blank=True)
    payment_status = models.CharField(max_length=20, default='pending')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Check-in Information
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_in_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='checked_in_registrations')
    check_in_method = models.CharField(max_length=20, default='manual')  # manual, qr_code, bulk
    
    # Feedback
    feedback_rating = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    feedback_comment = models.TextField(blank=True)
    feedback_submitted_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'event_registrations'
        verbose_name = 'Event Registration'
        verbose_name_plural = 'Event Registrations'
        unique_together = ['user', 'event']
        indexes = [
            models.Index(fields=['event', 'status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['checked_in_at']),
        ]
    
    def __str__(self):
        return f"{self.user.full_name} - {self.event.title}"
    
    def check_in(self, checked_in_by=None, method='manual'):
        """Check in user to event"""
        if self.status == 'registered':
            self.status = 'attended'
            self.checked_in_at = timezone.now()
            self.checked_in_by = checked_in_by
            self.check_in_method = method
            self.save()
            
            # Update event statistics
            self.event.total_attendees = self.event.registrations.filter(status='attended').count()
            self.event.save(update_fields=['total_attendees'])
            
            return True
        return False
    
    def cancel_registration(self):
        """Cancel event registration"""
        if self.status in ['registered', 'waitlisted']:
            self.status = 'cancelled'
            self.save()
            
            # Update event statistics
            self.event.total_registrations = self.event.registrations.filter(status__in=['registered', 'attended']).count()
            self.event.save(update_fields=['total_registrations'])
            
            return True
        return False
    
    def submit_feedback(self, rating, comment=""):
        """Submit event feedback"""
        self.feedback_rating = rating
        self.feedback_comment = comment
        self.feedback_submitted_at = timezone.now()
        self.save(update_fields=['feedback_rating', 'feedback_comment', 'feedback_submitted_at'])


class EventResource(models.Model):
    """Event resources and materials"""
    
    RESOURCE_TYPES = [
        ('document', 'Document'),
        ('presentation', 'Presentation'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('link', 'External Link'),
        ('image', 'Image'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='resource_files')
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES, default='document')
    
    # File or Link
    file = models.FileField(upload_to='event_resources/', blank=True, null=True)
    external_url = models.URLField(blank=True)
    
    # Access Control
    is_public = models.BooleanField(default=False)
    requires_registration = models.BooleanField(default=True)
    
    # Management
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    download_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'event_resources'
        verbose_name = 'Event Resource'
        verbose_name_plural = 'Event Resources'
        ordering = ['title']
    
    def __str__(self):
        return f"{self.event.title} - {self.title}"
    
    def can_user_access(self, user):
        """Check if user can access this resource"""
        if self.is_public:
            return True
        
        if not user.is_authenticated:
            return False
        
        if self.requires_registration:
            return self.event.registrations.filter(user=user, status__in=['registered', 'attended']).exists()
        
        # Club members can access
        return self.event.club.memberships.filter(user=user, status='active').exists()


class EventFeedback(models.Model):
    """Event feedback and reviews"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='feedback_entries')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    registration = models.ForeignKey(EventRegistration, on_delete=models.CASCADE, null=True, blank=True)
    
    # Ratings (1-5 scale)
    overall_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    content_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    organization_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    venue_rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    
    # Comments
    comment = models.TextField(blank=True)
    suggestions = models.TextField(blank=True)
    
    # Recommendations
    would_recommend = models.BooleanField(null=True, blank=True)
    would_attend_again = models.BooleanField(null=True, blank=True)
    
    # Additional Questions
    additional_feedback = models.JSONField(default=dict, blank=True)
    
    is_anonymous = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'event_feedback'
        verbose_name = 'Event Feedback'
        verbose_name_plural = 'Event Feedback'
        unique_together = ['event', 'user']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.event.title} - {self.overall_rating}★ by {self.user.full_name}"


# Signal handlers for event models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=EventRegistration)
def update_event_registration_count(sender, instance, **kwargs):
    """Update event registration statistics"""
    event = instance.event
    event.total_registrations = event.registrations.filter(status__in=['registered', 'attended']).count()
    event.total_attendees = event.registrations.filter(status='attended').count()
    
    # Calculate revenue
    total_revenue = event.registrations.filter(
        status__in=['registered', 'attended'],
        payment_status='completed'
    ).aggregate(total=models.Sum('amount_paid'))['total'] or Decimal('0.00')
    event.total_revenue = total_revenue
    
    event.save(update_fields=['total_registrations', 'total_attendees', 'total_revenue'])

@receiver(post_delete, sender=EventRegistration)
def update_event_stats_on_delete(sender, instance, **kwargs):
    """Update event statistics when registration is deleted"""
    try:
        event = instance.event
        event.total_registrations = event.registrations.filter(status__in=['registered', 'attended']).count()
        event.total_attendees = event.registrations.filter(status='attended').count()
        
        total_revenue = event.registrations.filter(
            status__in=['registered', 'attended'],
            payment_status='completed'
        ).aggregate(total=models.Sum('amount_paid'))['total'] or Decimal('0.00')
        event.total_revenue = total_revenue
        
        event.save(update_fields=['total_registrations', 'total_attendees', 'total_revenue'])
    except Event.DoesNotExist:
        pass

@receiver(post_save, sender=Event)
def update_club_event_count(sender, instance, created, **kwargs):
    """Update club's event count"""
    if created:
        club = instance.club
        club.total_events = club.events.filter(is_active=True).count()
        club.save(update_fields=['total_events'])

@receiver(post_delete, sender=Event)
def cleanup_event_files(sender, instance, **kwargs):
    """Clean up event files when deleted"""
    if instance.featured_image:
        try:
            instance.featured_image.delete(save=False)
        except Exception:
            pass
    
    if instance.qr_code:
        try:
            instance.qr_code.delete(save=False)
        except Exception:
            pass
