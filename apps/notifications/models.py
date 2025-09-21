"""
Notifications models for Campus Club Management Suite
Real-time notification system with multiple delivery channels
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid

class NotificationType(models.Model):
    """Types of notifications available"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=7, default="#007bff")
    
    # Default settings
    default_enabled = models.BooleanField(default=True)
    default_email_enabled = models.BooleanField(default=True)
    default_push_enabled = models.BooleanField(default=True)
    default_in_app_enabled = models.BooleanField(default=True)
    
    # Priority
    priority = models.IntegerField(default=1, help_text="1=High, 2=Medium, 3=Low")
    
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_types'
        verbose_name = 'Notification Type'
        verbose_name_plural = 'Notification Types'
        ordering = ['priority', 'name']
    
    def __str__(self):
        return self.name


class NotificationSettings(models.Model):
    """User's notification preferences"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_settings')
    
    # Global settings
    notifications_enabled = models.BooleanField(default=True)
    email_notifications_enabled = models.BooleanField(default=True)
    push_notifications_enabled = models.BooleanField(default=True)
    in_app_notifications_enabled = models.BooleanField(default=True)
    
    # Frequency settings
    email_frequency = models.CharField(
        max_length=20,
        choices=[
            ('immediate', 'Immediate'),
            ('hourly', 'Hourly'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('never', 'Never'),
        ],
        default='immediate'
    )
    
    # Quiet hours
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    
    # Type-specific settings (JSON field)
    type_settings = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_settings'
        verbose_name = 'Notification Settings'
        verbose_name_plural = 'Notification Settings'
    
    def __str__(self):
        return f"{self.user.full_name} - Notification Settings"
    
    def is_type_enabled(self, notification_type, channel='in_app'):
        """Check if a specific notification type and channel is enabled"""
        if not self.notifications_enabled:
            return False
        
        channel_enabled = getattr(self, f'{channel}_notifications_enabled', True)
        if not channel_enabled:
            return False
        
        # Check type-specific settings
        type_key = notification_type.name if hasattr(notification_type, 'name') else str(notification_type)
        type_config = self.type_settings.get(type_key, {})
        
        return type_config.get(f'{channel}_enabled', getattr(notification_type, f'default_{channel}_enabled', True))
    
    def is_in_quiet_hours(self):
        """Check if current time is in quiet hours"""
        if not self.quiet_hours_enabled or not self.quiet_hours_start or not self.quiet_hours_end:
            return False
        
        now_time = timezone.now().time()
        
        if self.quiet_hours_start <= self.quiet_hours_end:
            # Same day range
            return self.quiet_hours_start <= now_time <= self.quiet_hours_end
        else:
            # Overnight range
            return now_time >= self.quiet_hours_start or now_time <= self.quiet_hours_end


class Notification(models.Model):
    """Individual notification record"""
    
    PRIORITY_CHOICES = [
        (1, 'High'),
        (2, 'Medium'),
        (3, 'Low'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.ForeignKey(NotificationType, on_delete=models.CASCADE, related_name='notifications')
    
    # Content
    title = models.CharField(max_length=200)
    message = models.TextField()
    action_url = models.URLField(blank=True, help_text="URL to navigate when clicked")
    
    # Related object
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.UUIDField(null=True, blank=True)
    
    # Sender (optional)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_notifications')
    
    # Metadata
    data = models.JSONField(default=dict, blank=True, help_text="Additional data for the notification")
    
    # Settings
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Delivery channels
    send_email = models.BooleanField(default=True)
    send_push = models.BooleanField(default=True)
    send_in_app = models.BooleanField(default=True)
    
    # Timestamps
    scheduled_at = models.DateTimeField(null=True, blank=True, help_text="When to send the notification")
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Delivery status
    email_sent = models.BooleanField(default=False)
    push_sent = models.BooleanField(default=False)
    in_app_sent = models.BooleanField(default=True)  # Always true for in-app
    
    # Error tracking
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notifications'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'status']),
            models.Index(fields=['notification_type', 'created_at']),
            models.Index(fields=['scheduled_at']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} -> {self.recipient.full_name}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if self.status != 'read':
            self.status = 'read'
            self.read_at = timezone.now()
            self.save(update_fields=['status', 'read_at'])
    
    def mark_as_delivered(self):
        """Mark notification as delivered"""
        if self.status == 'sent':
            self.status = 'delivered'
            self.delivered_at = timezone.now()
            self.save(update_fields=['status', 'delivered_at'])
    
    def can_retry(self):
        """Check if notification can be retried"""
        return self.status == 'failed' and self.retry_count < self.max_retries
    
    def is_expired(self):
        """Check if notification has expired"""
        return self.expires_at and timezone.now() > self.expires_at
    
    @property
    def is_read(self):
        """Check if notification is read"""
        return self.status == 'read'
    
    @property
    def time_since_created(self):
        """Get time since creation"""
        return timezone.now() - self.created_at
    
    def get_related_object(self):
        """Get the related object for this notification"""
        if not self.related_object_type or not self.related_object_id:
            return None
        
        try:
            from django.apps import apps
            model_class = apps.get_model(self.related_object_type)
            return model_class.objects.get(id=self.related_object_id)
        except Exception:
            return None


class NotificationBatch(models.Model):
    """Batch notifications for bulk operations"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Recipients
    recipients = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='notification_batches')
    
    # Content template
    title_template = models.CharField(max_length=200)
    message_template = models.TextField()
    notification_type = models.ForeignKey(NotificationType, on_delete=models.CASCADE)
    
    # Settings
    scheduled_at = models.DateTimeField(null=True, blank=True)
    priority = models.IntegerField(choices=Notification.PRIORITY_CHOICES, default=2)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('scheduled', 'Scheduled'),
            ('sending', 'Sending'),
            ('sent', 'Sent'),
            ('failed', 'Failed'),
        ],
        default='draft'
    )
    
    # Delivery channels
    send_email = models.BooleanField(default=True)
    send_push = models.BooleanField(default=True)
    send_in_app = models.BooleanField(default=True)
    
    # Statistics
    total_recipients = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    
    # Timestamps
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_notification_batches')
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'notification_batches'
        verbose_name = 'Notification Batch'
        verbose_name_plural = 'Notification Batches'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.total_recipients} recipients)"
    
    def send_batch(self):
        """Send batch notifications"""
        if self.status != 'scheduled':
            return False
        
        self.status = 'sending'
        self.save()
        
        try:
            from .utils import create_notification
            
            for recipient in self.recipients.all():
                notification = create_notification(
                    recipient=recipient,
                    notification_type=self.notification_type,
                    title=self.title_template.format(user=recipient),
                    message=self.message_template.format(user=recipient),
                    priority=self.priority,
                    send_email=self.send_email,
                    send_push=self.send_push,
                    send_in_app=self.send_in_app,
                    scheduled_at=self.scheduled_at
                )
                
                if notification:
                    self.sent_count += 1
                else:
                    self.failed_count += 1
            
            self.status = 'sent'
            self.sent_at = timezone.now()
            self.save()
            
            return True
            
        except Exception as e:
            self.status = 'failed'
            self.save()
            return False


class PushNotificationDevice(models.Model):
    """User's push notification devices"""
    
    DEVICE_TYPES = [
        ('ios', 'iOS'),
        ('android', 'Android'),
        ('web', 'Web Browser'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='push_devices')
    
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES)
    device_token = models.TextField(unique=True)
    device_name = models.CharField(max_length=100, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(auto_now=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'push_notification_devices'
        verbose_name = 'Push Notification Device'
        verbose_name_plural = 'Push Notification Devices'
        unique_together = ['user', 'device_token']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.get_device_type_display()}"


# Signal handlers
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_notification_settings(sender, instance, created, **kwargs):
    """Create notification settings for new users"""
    if created:
        NotificationSettings.objects.get_or_create(user=instance)
