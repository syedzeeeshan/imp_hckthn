"""
Messaging models for Campus Club Management Suite
Direct messaging system with real-time capabilities
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid

class Conversation(models.Model):
    """Private conversation between users"""
    
    CONVERSATION_TYPES = [
        ('direct', 'Direct Message'),
        ('group', 'Group Chat'),
        ('club', 'Club Chat'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation_type = models.CharField(max_length=20, choices=CONVERSATION_TYPES, default='direct')
    name = models.CharField(max_length=100, blank=True, help_text="Name for group conversations")
    
    # Participants
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        through='ConversationParticipant', 
        related_name='conversations',
        through_fields=('conversation', 'user')
    )
    
    # Related objects
    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, null=True, blank=True, related_name='conversations')
    
    # Settings
    is_active = models.BooleanField(default=True)
    is_muted = models.BooleanField(default=False)
    
    # Tracking
    last_message_at = models.DateTimeField(null=True, blank=True)
    message_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'conversations'
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'
        ordering = ['-last_message_at', '-created_at']
        indexes = [
            models.Index(fields=['conversation_type', 'is_active']),
            models.Index(fields=['last_message_at']),
            models.Index(fields=['club']),
        ]
    
    def __str__(self):
        if self.name:
            return self.name
        elif self.conversation_type == 'direct':
            participants = self.participants.all()[:2]
            if participants:
                return f"Chat: {' & '.join(p.full_name for p in participants)}"
        return f"Conversation {self.id}"
    
    @property
    def display_name(self):
        """Get display name for conversation"""
        if self.name:
            return self.name
        elif self.conversation_type == 'club' and self.club:
            return f"{self.club.name} Chat"
        elif self.conversation_type == 'direct':
            participants = list(self.participants.all()[:2])
            if len(participants) == 2:
                return f"{participants[0].full_name} & {participants[1].full_name}"
            elif len(participants) == 1:
                return participants[0].full_name
        return "Untitled Conversation"
    
    def get_last_message(self):
        """Get the last message in this conversation"""
        return self.messages.filter(is_deleted=False).order_by('-created_at').first()
    
    def get_unread_count(self, user):
        """Get unread message count for a specific user"""
        participant = self.conversation_participants.filter(user=user).first()
        if not participant:
            return 0
        
        if not participant.last_read_at:
            return self.messages.filter(is_deleted=False).count()
        
        return self.messages.filter(
            is_deleted=False,
            created_at__gt=participant.last_read_at
        ).exclude(sender=user).count()
    
    def mark_as_read(self, user):
        """Mark conversation as read for a user"""
        participant, created = ConversationParticipant.objects.get_or_create(
            conversation=self, user=user
        )
        participant.last_read_at = timezone.now()
        participant.save()
    
    def add_participant(self, user, added_by=None):
        """Add a participant to the conversation"""
        participant, created = ConversationParticipant.objects.get_or_create(
            conversation=self,
            user=user,
            defaults={'added_by': added_by}
        )
        return participant, created
    
    def remove_participant(self, user):
        """Remove a participant from the conversation"""
        try:
            participant = self.conversation_participants.get(user=user)
            participant.left_at = timezone.now()
            participant.is_active = False
            participant.save()
            return True
        except ConversationParticipant.DoesNotExist:
            return False


class ConversationParticipant(models.Model):
    """Participant in a conversation"""
    
    ROLES = [
        ('member', 'Member'),
        ('admin', 'Admin'),
        ('owner', 'Owner'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='conversation_participants')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conversation_participations')
    
    # Participant settings
    role = models.CharField(max_length=20, choices=ROLES, default='member')
    is_active = models.BooleanField(default=True)
    is_muted = models.BooleanField(default=False)
    
    # Activity tracking
    last_read_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    
    # Management
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='added_participants')
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'conversation_participants'
        verbose_name = 'Conversation Participant'
        verbose_name_plural = 'Conversation Participants'
        unique_together = ['conversation', 'user']
        indexes = [
            models.Index(fields=['conversation', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.full_name} in {self.conversation}"


class Message(models.Model):
    """Individual message in a conversation"""
    
    MESSAGE_TYPES = [
        ('text', 'Text Message'),
        ('image', 'Image'),
        ('file', 'File'),
        ('system', 'System Message'),
        ('event', 'Event Notification'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    
    # Message content
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    content = models.TextField(blank=True)
    
    # Attachments
    attachment = models.FileField(upload_to='message_attachments/', null=True, blank=True)
    attachment_name = models.CharField(max_length=255, blank=True)
    attachment_size = models.BigIntegerField(null=True, blank=True)
    
    # Message status
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # Threading
    reply_to = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    
    # Reactions
    reactions = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'messages'
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['sender', 'created_at']),
            models.Index(fields=['message_type']),
            models.Index(fields=['is_deleted']),
        ]
    
    def __str__(self):
        if self.is_deleted:
            return "Deleted message"
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"{self.sender.full_name}: {content_preview}"
    
    def save(self, *args, **kwargs):
        # Update conversation last message timestamp
        if not self.is_deleted:
            self.conversation.last_message_at = timezone.now()
            self.conversation.message_count = models.F('message_count') + 1
            self.conversation.save(update_fields=['last_message_at', 'message_count'])
        
        super().save(*args, **kwargs)
    
    def delete_message(self, user=None):
        """Soft delete a message"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()
        
        # Update conversation message count
        self.conversation.message_count = models.F('message_count') - 1
        self.conversation.save(update_fields=['message_count'])
    
    def add_reaction(self, user, emoji):
        """Add a reaction to the message"""
        if emoji not in self.reactions:
            self.reactions[emoji] = []
        
        user_id = str(user.id)
        if user_id not in self.reactions[emoji]:
            self.reactions[emoji].append(user_id)
            self.save(update_fields=['reactions'])
            return True
        return False
    
    def remove_reaction(self, user, emoji):
        """Remove a reaction from the message"""
        if emoji in self.reactions:
            user_id = str(user.id)
            if user_id in self.reactions[emoji]:
                self.reactions[emoji].remove(user_id)
                if not self.reactions[emoji]:
                    del self.reactions[emoji]
                self.save(update_fields=['reactions'])
                return True
        return False
    
    @property
    def attachment_url(self):
        """Get attachment URL if exists"""
        if self.attachment:
            return self.attachment.url
        return None
    
    @property
    def is_system_message(self):
        """Check if this is a system message"""
        return self.message_type == 'system'


class MessageRead(models.Model):
    """Track message read status by users"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='read_by')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='read_messages')
    
    read_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'message_reads'
        verbose_name = 'Message Read'
        verbose_name_plural = 'Message Reads'
        unique_together = ['message', 'user']
        indexes = [
            models.Index(fields=['message', 'read_at']),
            models.Index(fields=['user', 'read_at']),
        ]
    
    def __str__(self):
        return f"{self.user.full_name} read message at {self.read_at}"


class BlockedUser(models.Model):
    """Users blocked from messaging each other"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    blocker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='blocked_users')
    blocked = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='blocked_by')
    
    reason = models.CharField(max_length=200, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'blocked_users'
        verbose_name = 'Blocked User'
        verbose_name_plural = 'Blocked Users'
        unique_together = ['blocker', 'blocked']
        indexes = [
            models.Index(fields=['blocker']),
            models.Index(fields=['blocked']),
        ]
    
    def __str__(self):
        return f"{self.blocker.full_name} blocked {self.blocked.full_name}"


class MessageReport(models.Model):
    """Report inappropriate messages"""
    
    REPORT_REASONS = [
        ('spam', 'Spam'),
        ('harassment', 'Harassment'),
        ('inappropriate', 'Inappropriate Content'),
        ('abusive', 'Abusive Language'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('reviewed', 'Reviewed'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reports')
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='message_reports')
    
    reason = models.CharField(max_length=20, choices=REPORT_REASONS)
    description = models.TextField(blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_reports')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'message_reports'
        verbose_name = 'Message Report'
        verbose_name_plural = 'Message Reports'
        unique_together = ['message', 'reporter']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Report by {self.reporter.full_name} - {self.get_reason_display()}"
