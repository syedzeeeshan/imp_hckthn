"""
Messaging utilities for Campus Club Management Suite
Helper functions for messaging operations
"""
from django.utils import timezone
from django.db.models import Q
from .models import Conversation, ConversationParticipant, BlockedUser

def can_users_message(user1, user2):
    """Check if two users can message each other"""
    if user1 == user2:
        return False
    
    # Check if either user has blocked the other
    blocked = BlockedUser.objects.filter(
        Q(blocker=user1, blocked=user2) |
        Q(blocker=user2, blocked=user1)
    ).exists()
    
    return not blocked

def get_or_create_direct_conversation(user1, user2):
    """Get or create a direct conversation between two users"""
    if not can_users_message(user1, user2):
        raise PermissionError("Users cannot message each other")
    
    # Try to find existing conversation
    conversation = Conversation.objects.filter(
        conversation_type='direct',
        conversation_participants__user=user1
    ).filter(
        conversation_participants__user=user2
    ).filter(
        conversation_participants__is_active=True
    ).first()
    
    if conversation:
        return conversation, False
    
    # Create new conversation
    conversation = Conversation.objects.create(
        conversation_type='direct'
    )
    
    # Add both users
    ConversationParticipant.objects.create(
        conversation=conversation,
        user=user1,
        role='member'
    )
    
    ConversationParticipant.objects.create(
        conversation=conversation,
        user=user2,
        role='member'
    )
    
    return conversation, True

def create_club_conversation(club, creator):
    """Create a club conversation"""
    conversation = Conversation.objects.create(
        conversation_type='club',
        name=f"{club.name} Chat",
        club=club
    )
    
    # Add creator as admin
    ConversationParticipant.objects.create(
        conversation=conversation,
        user=creator,
        role='admin',
        added_by=creator
    )
    
    # Add all active club members
    active_memberships = club.memberships.filter(status='active').select_related('user')
    
    for membership in active_memberships:
        if membership.user != creator:  # Creator already added
            role = 'admin' if membership.role in ['admin', 'leader'] else 'member'
            ConversationParticipant.objects.create(
                conversation=conversation,
                user=membership.user,
                role=role,
                added_by=creator
            )
    
    return conversation

def get_user_conversation_list(user, conversation_type=None):
    """Get list of conversations for a user"""
    queryset = Conversation.objects.filter(
        conversation_participants__user=user,
        conversation_participants__is_active=True,
        is_active=True
    ).select_related('club').prefetch_related(
        'conversation_participants__user',
        'messages'
    ).order_by('-last_message_at')
    
    if conversation_type:
        queryset = queryset.filter(conversation_type=conversation_type)
    
    return queryset.distinct()

def mark_messages_as_read(user, conversation, up_to_message=None):
    """Mark messages as read for a user in a conversation"""
    from .models import MessageRead
    
    messages_to_mark = conversation.messages.filter(
        is_deleted=False
    ).exclude(sender=user)
    
    if up_to_message:
        messages_to_mark = messages_to_mark.filter(created_at__lte=up_to_message.created_at)
    
    # Bulk create MessageRead objects
    message_reads = []
    for message in messages_to_mark:
        if not MessageRead.objects.filter(message=message, user=user).exists():
            message_reads.append(MessageRead(message=message, user=user))
    
    if message_reads:
        MessageRead.objects.bulk_create(message_reads, ignore_conflicts=True)
    
    # Update participant last_read_at
    participant = conversation.conversation_participants.filter(user=user).first()
    if participant:
        participant.last_read_at = timezone.now()
        participant.save(update_fields=['last_read_at'])

def get_conversation_unread_count(user, conversation):
    """Get unread message count for user in conversation"""
    participant = conversation.conversation_participants.filter(user=user).first()
    
    if not participant or not participant.last_read_at:
        # If never read, count all messages except user's own
        return conversation.messages.filter(is_deleted=False).exclude(sender=user).count()
    
    return conversation.messages.filter(
        is_deleted=False,
        created_at__gt=participant.last_read_at
    ).exclude(sender=user).count()

def search_conversations(user, query):
    """Search user's conversations"""
    if not query or len(query) < 2:
        return Conversation.objects.none()
    
    return Conversation.objects.filter(
        conversation_participants__user=user,
        conversation_participants__is_active=True,
        is_active=True
    ).filter(
        Q(name__icontains=query) |
        Q(conversation_participants__user__full_name__icontains=query)
    ).select_related('club').prefetch_related(
        'conversation_participants__user'
    ).distinct()

def search_messages(user, query):
    """Search user's messages"""
    if not query or len(query) < 2:
        return []
    
    from .models import Message
    
    return Message.objects.filter(
        conversation__conversation_participants__user=user,
        conversation__conversation_participants__is_active=True,
        is_deleted=False,
        content__icontains=query
    ).select_related('sender', 'conversation').order_by('-created_at')[:50]

def get_popular_emojis():
    """Get list of popular emojis for reactions"""
    return ['👍', '👎', '❤️', '😂', '😮', '😢', '😡', '🎉', '👏', '🔥']

def validate_message_content(content, message_type='text'):
    """Validate message content"""
    if message_type == 'text':
        if not content or not content.strip():
            return False, "Text messages cannot be empty"
        
        if len(content) > 5000:  # 5000 character limit
            return False, "Message is too long (max 5000 characters)"
    
    return True, None

def get_conversation_analytics(conversation):
    """Get analytics for a conversation"""
    from django.db.models import Count, Avg
    
    total_messages = conversation.messages.filter(is_deleted=False).count()
    
    # Message distribution by user
    message_by_user = conversation.messages.filter(
        is_deleted=False
    ).values('sender__full_name').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Activity by day
    from django.db.models import DateField
    from django.db.models.functions import Cast
    
    messages_by_day = conversation.messages.filter(
        is_deleted=False
    ).extra(
        select={'day': 'date(created_at)'}
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    return {
        'total_messages': total_messages,
        'total_participants': conversation.conversation_participants.filter(is_active=True).count(),
        'messages_by_user': list(message_by_user),
        'messages_by_day': list(messages_by_day),
        'created_at': conversation.created_at,
        'last_message_at': conversation.last_message_at
    }
