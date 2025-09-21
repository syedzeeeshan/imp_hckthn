"""
Messaging serializers for Campus Club Management Suite
Seamless API serialization for messaging system
"""
from rest_framework import serializers
from django.utils import timezone
from django.db.models import Q
from apps.authentication.serializers import UserSerializer
from .models import (
    Conversation, ConversationParticipant, Message, MessageRead,
    BlockedUser, MessageReport
)

class ConversationParticipantSerializer(serializers.ModelSerializer):
    """Serializer for ConversationParticipant model"""
    
    user = UserSerializer(read_only=True)
    added_by = UserSerializer(read_only=True)
    is_online = serializers.SerializerMethodField()
    
    class Meta:
        model = ConversationParticipant
        fields = [
            'id', 'user', 'role', 'is_active', 'is_muted',
            'last_read_at', 'last_seen_at', 'added_by', 'joined_at',
            'left_at', 'is_online'
        ]
        read_only_fields = [
            'id', 'user', 'added_by', 'joined_at', 'left_at', 'is_online'
        ]
    
    def get_is_online(self, obj):
        """Check if user is currently online"""
        if obj.last_seen_at:
            return (timezone.now() - obj.last_seen_at).seconds < 300  # 5 minutes
        return False


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message model"""
    
    sender = UserSerializer(read_only=True)
    reply_to = serializers.SerializerMethodField()
    attachment_url = serializers.ReadOnlyField()
    is_system_message = serializers.ReadOnlyField()
    read_by_count = serializers.SerializerMethodField()
    reactions_display = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'sender', 'message_type', 'content', 'attachment',
            'attachment_name', 'attachment_size', 'attachment_url',
            'is_edited', 'is_deleted', 'deleted_at', 'reply_to',
            'reactions', 'reactions_display', 'is_system_message',
            'read_by_count', 'can_edit', 'can_delete', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'sender', 'attachment_url', 'is_system_message',
            'is_edited', 'is_deleted', 'deleted_at', 'reactions_display',
            'read_by_count', 'can_edit', 'can_delete', 'created_at', 'updated_at'
        ]
    
    def get_reply_to(self, obj):
        """Get replied message details"""
        if obj.reply_to:
            return {
                'id': str(obj.reply_to.id),
                'content': obj.reply_to.content[:100] + "..." if len(obj.reply_to.content) > 100 else obj.reply_to.content,
                'sender_name': obj.reply_to.sender.full_name,
                'created_at': obj.reply_to.created_at
            }
        return None
    
    def get_read_by_count(self, obj):
        """Get count of users who read this message"""
        return obj.read_by.count()
    
    def get_reactions_display(self, obj):
        """Get reactions in display format"""
        reactions_display = []
        for emoji, user_ids in obj.reactions.items():
            reactions_display.append({
                'emoji': emoji,
                'count': len(user_ids),
                'users': user_ids
            })
        return reactions_display
    
    def get_can_edit(self, obj):
        """Check if current user can edit this message"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Users can edit their own messages within 15 minutes
            if obj.sender == request.user:
                time_diff = timezone.now() - obj.created_at
                return time_diff.total_seconds() < 900  # 15 minutes
        return False
    
    def get_can_delete(self, obj):
        """Check if current user can delete this message"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Users can delete their own messages
            # Conversation admins can delete any message
            if obj.sender == request.user:
                return True
            
            participant = obj.conversation.conversation_participants.filter(
                user=request.user, role__in=['admin', 'owner']
            ).first()
            return participant is not None
        return False


class ConversationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for conversation listings"""
    
    display_name = serializers.ReadOnlyField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    participants = ConversationParticipantSerializer(source='conversation_participants', many=True, read_only=True)
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'conversation_type', 'name', 'display_name', 'is_active',
            'is_muted', 'last_message_at', 'message_count', 'last_message',
            'unread_count', 'participants', 'created_at'
        ]
        read_only_fields = [
            'id', 'display_name', 'last_message_at', 'message_count',
            'last_message', 'unread_count', 'participants', 'created_at'
        ]
    
    def get_last_message(self, obj):
        """Get last message preview"""
        last_message = obj.get_last_message()
        if last_message:
            return MessageSerializer(last_message, context=self.context).data
        return None
    
    def get_unread_count(self, obj):
        """Get unread count for current user"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.get_unread_count(request.user)
        return 0


class ConversationDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for conversation details"""
    
    display_name = serializers.ReadOnlyField()
    participants = ConversationParticipantSerializer(source='conversation_participants', many=True, read_only=True)
    recent_messages = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'conversation_type', 'name', 'display_name', 'is_active',
            'is_muted', 'last_message_at', 'message_count', 'participants',
            'recent_messages', 'unread_count', 'can_manage', 'user_role',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'display_name', 'last_message_at', 'message_count',
            'participants', 'recent_messages', 'unread_count', 'can_manage',
            'user_role', 'created_at', 'updated_at'
        ]
    
    def get_recent_messages(self, obj):
        """Get recent messages"""
        messages = obj.messages.filter(is_deleted=False).order_by('-created_at')[:20]
        return MessageSerializer(messages, many=True, context=self.context).data
    
    def get_unread_count(self, obj):
        """Get unread count for current user"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.get_unread_count(request.user)
        return 0
    
    def get_can_manage(self, obj):
        """Check if current user can manage this conversation"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            participant = obj.conversation_participants.filter(user=request.user).first()
            return participant and participant.role in ['admin', 'owner']
        return False
    
    def get_user_role(self, obj):
        """Get current user's role in conversation"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            participant = obj.conversation_participants.filter(user=request.user).first()
            return participant.role if participant else None
        return None


class ConversationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating conversations"""
    
    participant_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=True
    )
    
    class Meta:
        model = Conversation
        fields = ['conversation_type', 'name', 'participant_ids']
    
    def validate_participant_ids(self, value):
        """Validate participant IDs"""
        if not value:
            raise serializers.ValidationError("At least one participant is required")
        
        # Check if users exist
        from apps.authentication.models import User
        existing_users = User.objects.filter(id__in=value, is_active=True)
        if len(existing_users) != len(value):
            raise serializers.ValidationError("One or more participants not found")
        
        return value
    
    def validate(self, attrs):
        """Cross-field validation"""
        conversation_type = attrs.get('conversation_type')
        participant_ids = attrs.get('participant_ids', [])
        
        if conversation_type == 'direct' and len(participant_ids) != 1:
            raise serializers.ValidationError("Direct conversations must have exactly 1 other participant")
        
        if conversation_type == 'group' and len(participant_ids) < 2:
            raise serializers.ValidationError("Group conversations must have at least 2 participants")
        
        return attrs
    
    def create(self, validated_data):
        """Create conversation with participants"""
        participant_ids = validated_data.pop('participant_ids')
        creator = self.context['request'].user
        
        # Create conversation
        conversation = Conversation.objects.create(**validated_data)
        
        # Add creator as owner
        conversation.add_participant(creator)
        creator_participant = conversation.conversation_participants.get(user=creator)
        creator_participant.role = 'owner'
        creator_participant.save()
        
        # Add other participants
        from apps.authentication.models import User
        for participant_id in participant_ids:
            user = User.objects.get(id=participant_id)
            conversation.add_participant(user, added_by=creator)
        
        return conversation


class MessageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating messages"""
    
    reply_to_id = serializers.UUIDField(required=False, write_only=True)
    
    class Meta:
        model = Message
        fields = ['content', 'message_type', 'attachment', 'reply_to_id']
    
    def validate_reply_to_id(self, value):
        """Validate reply message exists and is in same conversation"""
        if value:
            conversation = self.context.get('conversation')
            try:
                reply_message = Message.objects.get(id=value, conversation=conversation, is_deleted=False)
                return value
            except Message.DoesNotExist:
                raise serializers.ValidationError("Reply message not found in this conversation")
        return value
    
    def validate(self, attrs):
        """Validate message content"""
        content = attrs.get('content', '').strip()
        attachment = attrs.get('attachment')
        message_type = attrs.get('message_type', 'text')
        
        if message_type == 'text' and not content and not attachment:
            raise serializers.ValidationError("Text messages must have content or attachment")
        
        return attrs
    
    def create(self, validated_data):
        """Create message"""
        reply_to_id = validated_data.pop('reply_to_id', None)
        conversation = self.context['conversation']
        sender = self.context['request'].user
        
        # Set reply_to if provided
        reply_to = None
        if reply_to_id:
            try:
                reply_to = Message.objects.get(id=reply_to_id, conversation=conversation)
            except Message.DoesNotExist:
                pass
        
        message = Message.objects.create(
            conversation=conversation,
            sender=sender,
            reply_to=reply_to,
            **validated_data
        )
        
        return message


class BlockedUserSerializer(serializers.ModelSerializer):
    """Serializer for BlockedUser model"""
    
    blocker = UserSerializer(read_only=True)
    blocked = UserSerializer(read_only=True)
    
    class Meta:
        model = BlockedUser
        fields = ['id', 'blocker', 'blocked', 'reason', 'created_at']
        read_only_fields = ['id', 'blocker', 'blocked', 'created_at']


class MessageReportSerializer(serializers.ModelSerializer):
    """Serializer for MessageReport model"""
    
    reporter = UserSerializer(read_only=True)
    reviewed_by = UserSerializer(read_only=True)
    message_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = MessageReport
        fields = [
            'id', 'reason', 'description', 'status', 'reporter',
            'reviewed_by', 'reviewed_at', 'resolution_notes',
            'message_preview', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'reporter', 'reviewed_by', 'reviewed_at',
            'message_preview', 'created_at', 'updated_at'
        ]
    
    def get_message_preview(self, obj):
        """Get preview of reported message"""
        if obj.message and not obj.message.is_deleted:
            content = obj.message.content[:100] + "..." if len(obj.message.content) > 100 else obj.message.content
            return {
                'id': str(obj.message.id),
                'content': content,
                'sender': obj.message.sender.full_name,
                'created_at': obj.message.created_at
            }
        return None


class MessageReactionSerializer(serializers.Serializer):
    """Serializer for message reactions"""
    
    emoji = serializers.CharField(max_length=10)
    action = serializers.ChoiceField(choices=['add', 'remove'])
    
    def validate_emoji(self, value):
        """Validate emoji format"""
        # Basic emoji validation - you could make this more sophisticated
        allowed_emojis = ['👍', '👎', '❤️', '😂', '😮', '😢', '😡', '🎉']
        if value not in allowed_emojis:
            raise serializers.ValidationError("Invalid emoji")
        return value


class ConversationSettingsSerializer(serializers.Serializer):
    """Serializer for conversation settings"""
    
    is_muted = serializers.BooleanField(required=False)
    name = serializers.CharField(max_length=100, required=False)
    
    def validate_name(self, value):
        """Validate conversation name"""
        if value and len(value.strip()) < 3:
            raise serializers.ValidationError("Conversation name must be at least 3 characters")
        return value.strip() if value else value
