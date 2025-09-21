"""
Messaging views for Campus Club Management Suite
Seamless API endpoints for direct messaging and conversations
"""
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Max
from django.utils import timezone
from django.core.exceptions import PermissionDenied

from .models import (
    Conversation, ConversationParticipant, Message, MessageRead,
    BlockedUser, MessageReport
)
from .serializers import (
    ConversationListSerializer, ConversationDetailSerializer, ConversationCreateSerializer,
    MessageSerializer, MessageCreateSerializer, ConversationParticipantSerializer,
    BlockedUserSerializer, MessageReportSerializer, MessageReactionSerializer,
    ConversationSettingsSerializer
)
from apps.authentication.models import User


class ConversationListView(generics.ListCreateAPIView):
    """List and create conversations"""
    
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ConversationCreateSerializer
        return ConversationListSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        # Get conversations user is participating in
        queryset = Conversation.objects.filter(
            conversation_participants__user=user,
            conversation_participants__is_active=True,
            is_active=True
        ).select_related('club').prefetch_related(
            'conversation_participants__user',
            'messages'
        ).annotate(
            latest_message_time=Max('messages__created_at')
        ).order_by('-latest_message_time', '-created_at')
        
        # Filter by conversation type
        conversation_type = self.request.query_params.get('type')
        if conversation_type:
            queryset = queryset.filter(conversation_type=conversation_type)
        
        # Filter by search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(conversation_participants__user__full_name__icontains=search)
            ).distinct()
        
        return queryset.distinct()
    
    def perform_create(self, serializer):
        # Check if user is blocked by any participants
        participant_ids = serializer.validated_data.get('participant_ids', [])
        user = self.request.user
        
        # Check for existing direct conversation
        if serializer.validated_data['conversation_type'] == 'direct':
            other_user_id = participant_ids[0]
            existing_conversation = Conversation.objects.filter(
                conversation_type='direct',
                conversation_participants__user=user
            ).filter(
                conversation_participants__user_id=other_user_id
            ).first()
            
            if existing_conversation:
                raise serializers.ValidationError({
                    'non_field_errors': ['Direct conversation with this user already exists']
                })
            
            # Check if users have blocked each other
            if BlockedUser.objects.filter(
                Q(blocker=user, blocked_id=other_user_id) |
                Q(blocker_id=other_user_id, blocked=user)
            ).exists():
                raise PermissionDenied("Cannot create conversation with blocked user")
        
        serializer.save()


class ConversationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Conversation detail view"""
    
    serializer_class = ConversationDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        user = self.request.user
        return Conversation.objects.filter(
            conversation_participants__user=user,
            conversation_participants__is_active=True,
            is_active=True
        ).select_related('club').prefetch_related(
            'conversation_participants__user',
            'messages__sender'
        )
    
    def retrieve(self, request, *args, **kwargs):
        """Mark conversation as read when retrieving"""
        conversation = self.get_object()
        conversation.mark_as_read(request.user)
        return super().retrieve(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """Update conversation settings"""
        conversation = self.get_object()
        
        # Check permissions
        participant = conversation.conversation_participants.filter(user=request.user).first()
        if not participant or participant.role not in ['admin', 'owner']:
            return Response({
                'error': 'You do not have permission to update this conversation'
            }, status=status.HTTP_403_FORBIDDEN)
        
        return super().update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """Leave conversation"""
        conversation = self.get_object()
        
        # Remove user from conversation
        participant = conversation.conversation_participants.filter(user=request.user).first()
        if participant:
            participant.is_active = False
            participant.left_at = timezone.now()
            participant.save()
            
            return Response({
                'message': 'Successfully left the conversation'
            }, status=status.HTTP_200_OK)
        
        return Response({
            'error': 'You are not a participant in this conversation'
        }, status=status.HTTP_400_BAD_REQUEST)


class ConversationMessagesView(generics.ListCreateAPIView):
    """List and create messages in a conversation"""
    
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return MessageCreateSerializer
        return MessageSerializer
    
    def get_queryset(self):
        conversation_id = self.kwargs.get('conversation_id')
        user = self.request.user
        
        # Verify user is participant
        try:
            conversation = Conversation.objects.get(
                id=conversation_id,
                conversation_participants__user=user,
                conversation_participants__is_active=True
            )
        except Conversation.DoesNotExist:
            return Message.objects.none()
        
        queryset = conversation.messages.filter(is_deleted=False).select_related(
            'sender', 'reply_to__sender'
        ).prefetch_related('read_by__user')
        
        # Pagination cursor
        before = self.request.query_params.get('before')
        if before:
            try:
                from datetime import datetime
                before_date = datetime.fromisoformat(before.replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__lt=before_date)
            except (ValueError, TypeError):
                pass
        
        return queryset.order_by('-created_at')[:50]  # Last 50 messages
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        conversation_id = self.kwargs.get('conversation_id')
        
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            context['conversation'] = conversation
        except Conversation.DoesNotExist:
            pass
        
        return context
    
    def perform_create(self, serializer):
        conversation_id = self.kwargs.get('conversation_id')
        user = self.request.user
        
        # Verify conversation and permissions
        try:
            conversation = Conversation.objects.get(
                id=conversation_id,
                conversation_participants__user=user,
                conversation_participants__is_active=True
            )
        except Conversation.DoesNotExist:
            raise PermissionDenied("You do not have access to this conversation")
        
        # Check if user is blocked by any participants
        participants = conversation.conversation_participants.filter(is_active=True).exclude(user=user)
        for participant in participants:
            if BlockedUser.objects.filter(blocker=participant.user, blocked=user).exists():
                raise PermissionDenied("You are blocked by a participant in this conversation")
        
        message = serializer.save()
        
        # Mark message as read by sender
        MessageRead.objects.get_or_create(message=message, user=user)


class MessageDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Message detail view"""
    
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(
            conversation__conversation_participants__user=user,
            conversation__conversation_participants__is_active=True,
            is_deleted=False
        ).select_related('sender', 'conversation')
    
    def update(self, request, *args, **kwargs):
        """Update message content"""
        message = self.get_object()
        
        # Check permissions
        if message.sender != request.user:
            return Response({
                'error': 'You can only edit your own messages'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Check time limit (15 minutes)
        time_diff = timezone.now() - message.created_at
        if time_diff.total_seconds() > 900:  # 15 minutes
            return Response({
                'error': 'Messages can only be edited within 15 minutes of posting'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Only allow content updates
        allowed_fields = ['content']
        data = {key: value for key, value in request.data.items() if key in allowed_fields}
        
        serializer = self.get_serializer(message, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(is_edited=True)
        
        return Response(serializer.data)
    
    def destroy(self, request, *args, **kwargs):
        """Delete message"""
        message = self.get_object()
        
        # Check permissions
        user = request.user
        can_delete = (
            message.sender == user or
            message.conversation.conversation_participants.filter(
                user=user, role__in=['admin', 'owner']
            ).exists()
        )
        
        if not can_delete:
            return Response({
                'error': 'You do not have permission to delete this message'
            }, status=status.HTTP_403_FORBIDDEN)
        
        message.delete_message(user)
        
        return Response({
            'message': 'Message deleted successfully'
        }, status=status.HTTP_200_OK)


class MessageReactionView(APIView):
    """Add or remove reactions to messages"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, message_id):
        try:
            message = Message.objects.get(
                id=message_id,
                conversation__conversation_participants__user=request.user,
                conversation__conversation_participants__is_active=True,
                is_deleted=False
            )
        except Message.DoesNotExist:
            return Response({
                'error': 'Message not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = MessageReactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        emoji = serializer.validated_data['emoji']
        action = serializer.validated_data['action']
        
        if action == 'add':
            success = message.add_reaction(request.user, emoji)
            message_text = 'Reaction added' if success else 'Reaction already exists'
        else:  # remove
            success = message.remove_reaction(request.user, emoji)
            message_text = 'Reaction removed' if success else 'Reaction not found'
        
        return Response({
            'message': message_text,
            'reactions': message.reactions
        }, status=status.HTTP_200_OK)


class ConversationParticipantsView(generics.ListAPIView):
    """List conversation participants"""
    
    serializer_class = ConversationParticipantSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        conversation_id = self.kwargs.get('conversation_id')
        user = self.request.user
        
        # Verify user is participant
        try:
            conversation = Conversation.objects.get(
                id=conversation_id,
                conversation_participants__user=user,
                conversation_participants__is_active=True
            )
        except Conversation.DoesNotExist:
            return ConversationParticipant.objects.none()
        
        return conversation.conversation_participants.filter(is_active=True).select_related('user', 'added_by')


class AddParticipantView(APIView):
    """Add participant to group conversation"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, conversation_id):
        try:
            conversation = Conversation.objects.get(
                id=conversation_id,
                conversation_participants__user=request.user,
                conversation_participants__is_active=True
            )
        except Conversation.DoesNotExist:
            return Response({
                'error': 'Conversation not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check permissions
        user_participant = conversation.conversation_participants.filter(user=request.user).first()
        if not user_participant or user_participant.role not in ['admin', 'owner']:
            return Response({
                'error': 'You do not have permission to add participants'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Only allow adding to group conversations
        if conversation.conversation_type != 'group':
            return Response({
                'error': 'Can only add participants to group conversations'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({
                'error': 'user_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user_to_add = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user is already a participant
        if conversation.conversation_participants.filter(user=user_to_add, is_active=True).exists():
            return Response({
                'error': 'User is already a participant'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if users have blocked each other
        if BlockedUser.objects.filter(
            Q(blocker=request.user, blocked=user_to_add) |
            Q(blocker=user_to_add, blocked=request.user)
        ).exists():
            return Response({
                'error': 'Cannot add blocked user'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Add participant
        participant, created = conversation.add_participant(user_to_add, added_by=request.user)
        
        return Response({
            'message': f'{user_to_add.full_name} added to conversation',
            'participant': ConversationParticipantSerializer(participant).data
        }, status=status.HTTP_201_CREATED)


class RemoveParticipantView(APIView):
    """Remove participant from group conversation"""
    
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, conversation_id, participant_id):
        try:
            conversation = Conversation.objects.get(
                id=conversation_id,
                conversation_participants__user=request.user,
                conversation_participants__is_active=True
            )
        except Conversation.DoesNotExist:
            return Response({
                'error': 'Conversation not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check permissions
        user_participant = conversation.conversation_participants.filter(user=request.user).first()
        if not user_participant or user_participant.role not in ['admin', 'owner']:
            return Response({
                'error': 'You do not have permission to remove participants'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            participant_to_remove = conversation.conversation_participants.get(
                id=participant_id,
                is_active=True
            )
        except ConversationParticipant.DoesNotExist:
            return Response({
                'error': 'Participant not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Cannot remove owner
        if participant_to_remove.role == 'owner':
            return Response({
                'error': 'Cannot remove conversation owner'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Remove participant
        participant_to_remove.is_active = False
        participant_to_remove.left_at = timezone.now()
        participant_to_remove.save()
        
        return Response({
            'message': f'{participant_to_remove.user.full_name} removed from conversation'
        }, status=status.HTTP_200_OK)


class BlockUserView(APIView):
    """Block a user from messaging"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user_id = request.data.get('user_id')
        reason = request.data.get('reason', '')
        
        if not user_id:
            return Response({
                'error': 'user_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user_to_block = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if user_to_block == request.user:
            return Response({
                'error': 'Cannot block yourself'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        blocked_user, created = BlockedUser.objects.get_or_create(
            blocker=request.user,
            blocked=user_to_block,
            defaults={'reason': reason}
        )
        
        if not created:
            return Response({
                'error': 'User is already blocked'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'message': f'{user_to_block.full_name} has been blocked',
            'blocked_user': BlockedUserSerializer(blocked_user).data
        }, status=status.HTTP_201_CREATED)


class UnblockUserView(APIView):
    """Unblock a user"""
    
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, user_id):
        try:
            blocked_user = BlockedUser.objects.get(
                blocker=request.user,
                blocked_id=user_id
            )
        except BlockedUser.DoesNotExist:
            return Response({
                'error': 'User is not blocked'
            }, status=status.HTTP_404_NOT_FOUND)
        
        user_name = blocked_user.blocked.full_name
        blocked_user.delete()
        
        return Response({
            'message': f'{user_name} has been unblocked'
        }, status=status.HTTP_200_OK)


class BlockedUsersListView(generics.ListAPIView):
    """List blocked users"""
    
    serializer_class = BlockedUserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return BlockedUser.objects.filter(blocker=self.request.user).select_related('blocked')


class ReportMessageView(APIView):
    """Report a message"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, message_id):
        try:
            message = Message.objects.get(
                id=message_id,
                conversation__conversation_participants__user=request.user,
                conversation__conversation_participants__is_active=True,
                is_deleted=False
            )
        except Message.DoesNotExist:
            return Response({
                'error': 'Message not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Cannot report own messages
        if message.sender == request.user:
            return Response({
                'error': 'Cannot report your own message'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = MessageReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        report, created = MessageReport.objects.get_or_create(
            message=message,
            reporter=request.user,
            defaults={
                'reason': serializer.validated_data['reason'],
                'description': serializer.validated_data.get('description', '')
            }
        )
        
        if not created:
            return Response({
                'error': 'You have already reported this message'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'message': 'Message reported successfully',
            'report': MessageReportSerializer(report).data
        }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def conversation_search(request):
    """Search for conversations and messages"""
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 2:
        return Response({
            'conversations': [],
            'messages': []
        })
    
    user = request.user
    
    # Search conversations
    conversations = Conversation.objects.filter(
        conversation_participants__user=user,
        conversation_participants__is_active=True,
        is_active=True
    ).filter(
        Q(name__icontains=query) |
        Q(conversation_participants__user__full_name__icontains=query)
    ).select_related('club').prefetch_related('conversation_participants__user').distinct()[:10]
    
    # Search messages
    messages = Message.objects.filter(
        conversation__conversation_participants__user=user,
        conversation__conversation_participants__is_active=True,
        is_deleted=False,
        content__icontains=query
    ).select_related('sender', 'conversation').order_by('-created_at')[:20]
    
    return Response({
        'conversations': ConversationListSerializer(conversations, many=True, context={'request': request}).data,
        'messages': MessageSerializer(messages, many=True, context={'request': request}).data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def messaging_stats(request):
    """Get messaging statistics for current user"""
    user = request.user
    
    # Basic stats
    total_conversations = Conversation.objects.filter(
        conversation_participants__user=user,
        conversation_participants__is_active=True,
        is_active=True
    ).count()
    
    total_messages_sent = Message.objects.filter(sender=user, is_deleted=False).count()
    
    unread_count = 0
    for conversation in Conversation.objects.filter(
        conversation_participants__user=user,
        conversation_participants__is_active=True
    ):
        unread_count += conversation.get_unread_count(user)
    
    # Recent activity
    recent_conversations = Conversation.objects.filter(
        conversation_participants__user=user,
        conversation_participants__is_active=True,
        last_message_at__isnull=False
    ).order_by('-last_message_at')[:5]
    
    return Response({
        'total_conversations': total_conversations,
        'total_messages_sent': total_messages_sent,
        'total_unread': unread_count,
        'blocked_users_count': BlockedUser.objects.filter(blocker=user).count(),
        'recent_conversations': ConversationListSerializer(
            recent_conversations, 
            many=True, 
            context={'request': request}
        ).data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_conversation_read(request, conversation_id):
    """Mark all messages in conversation as read"""
    try:
        conversation = Conversation.objects.get(
            id=conversation_id,
            conversation_participants__user=request.user,
            conversation_participants__is_active=True
        )
    except Conversation.DoesNotExist:
        return Response({
            'error': 'Conversation not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    conversation.mark_as_read(request.user)
    
    return Response({
        'message': 'Conversation marked as read'
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_conversation_settings(request, conversation_id):
    """Update conversation settings"""
    try:
        conversation = Conversation.objects.get(
            id=conversation_id,
            conversation_participants__user=request.user,
            conversation_participants__is_active=True
        )
    except Conversation.DoesNotExist:
        return Response({
            'error': 'Conversation not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = ConversationSettingsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    # Update participant settings
    participant = conversation.conversation_participants.get(user=request.user)
    
    if 'is_muted' in serializer.validated_data:
        participant.is_muted = serializer.validated_data['is_muted']
        participant.save()
    
    # Update conversation name (admin only)
    if 'name' in serializer.validated_data and participant.role in ['admin', 'owner']:
        conversation.name = serializer.validated_data['name']
        conversation.save()
    
    return Response({
        'message': 'Settings updated successfully',
        'conversation': ConversationDetailSerializer(conversation, context={'request': request}).data
    })
