"""
Notifications views for Campus Club Management Suite
Seamless API endpoints for notification system
"""
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count
from django.utils import timezone

from .models import (
    NotificationType, NotificationSettings, Notification,
    NotificationBatch, PushNotificationDevice
)
from .serializers import (
    NotificationTypeSerializer, NotificationSettingsSerializer,
    NotificationSerializer, NotificationListSerializer, NotificationCreateSerializer,
    NotificationBatchSerializer, PushNotificationDeviceSerializer,
    NotificationStatsSerializer, NotificationPreferencesSerializer,
    BulkNotificationActionSerializer
)


class NotificationTypeListView(generics.ListAPIView):
    """List all notification types"""
    
    queryset = NotificationType.objects.filter(is_active=True).order_by('priority', 'name')
    serializer_class = NotificationTypeSerializer
    permission_classes = [IsAuthenticated]


class NotificationSettingsView(generics.RetrieveUpdateAPIView):
    """Get and update user notification settings"""
    
    serializer_class = NotificationSettingsSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        settings, created = NotificationSettings.objects.get_or_create(
            user=self.request.user
        )
        return settings


class NotificationListView(generics.ListAPIView):
    """List user's notifications"""
    
    serializer_class = NotificationListSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = Notification.objects.filter(
            recipient=user,
            in_app_sent=True
        ).select_related('notification_type', 'sender')
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter == 'unread':
            queryset = queryset.exclude(status='read')
        elif status_filter == 'read':
            queryset = queryset.filter(status='read')
        
        # Filter by type
        type_filter = self.request.query_params.get('type')
        if type_filter:
            queryset = queryset.filter(notification_type__name=type_filter)
        
        # Filter by priority
        priority_filter = self.request.query_params.get('priority')
        if priority_filter:
            queryset = queryset.filter(priority=priority_filter)
        
        # Exclude expired notifications
        queryset = queryset.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )
        
        return queryset.order_by('-created_at')


class NotificationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Notification detail view"""
    
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return Notification.objects.filter(
            recipient=self.request.user,
            in_app_sent=True
        ).select_related('notification_type', 'sender')
    
    def retrieve(self, request, *args, **kwargs):
        """Mark notification as read when retrieving"""
        notification = self.get_object()
        if not notification.is_read:
            notification.mark_as_read()
        return super().retrieve(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """Only allow marking as read/unread"""
        notification = self.get_object()
        action = request.data.get('action')
        
        if action == 'mark_read':
            notification.mark_as_read()
        elif action == 'mark_unread':
            notification.status = 'delivered'
            notification.read_at = None
            notification.save()
        else:
            return Response({
                'error': 'Invalid action. Use "mark_read" or "mark_unread"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'message': f'Notification marked as {action.split("_")[1]}',
            'notification': NotificationSerializer(notification, context={'request': request}).data
        })
    
    def destroy(self, request, *args, **kwargs):
        """Soft delete notification"""
        notification = self.get_object()
        notification.status = 'read'  # Mark as read instead of deleting
        notification.read_at = timezone.now()
        notification.save()
        
        return Response({
            'message': 'Notification deleted successfully'
        }, status=status.HTTP_200_OK)


class CreateNotificationView(generics.CreateAPIView):
    """Create notification (admin only)"""
    
    serializer_class = NotificationCreateSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        # Check permissions
        user = self.request.user
        can_create = (
            (hasattr(user, 'is_super_admin') and user.is_super_admin) or
            (hasattr(user, 'is_college_admin') and user.is_college_admin)
        )
        
        if not can_create:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only admins can create notifications")
        
        serializer.save()


class PushDeviceView(generics.ListCreateAPIView):
    """Manage push notification devices"""
    
    serializer_class = PushNotificationDeviceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return PushNotificationDevice.objects.filter(
            user=self.request.user,
            is_active=True
        ).order_by('-last_used_at')


class UpdateNotificationPreferencesView(APIView):
    """Update notification preferences for specific types"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = NotificationPreferencesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        settings, created = NotificationSettings.objects.get_or_create(user=user)
        
        notification_type_id = serializer.validated_data['notification_type_id']
        
        # Get notification type
        try:
            notification_type = NotificationType.objects.get(id=notification_type_id)
        except NotificationType.DoesNotExist:
            return Response({
                'error': 'Notification type not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Update type-specific settings
        if not settings.type_settings:
            settings.type_settings = {}
        
        type_key = notification_type.name
        settings.type_settings[type_key] = {
            'enabled': serializer.validated_data['enabled'],
            'email_enabled': serializer.validated_data.get('email_enabled', True),
            'push_enabled': serializer.validated_data.get('push_enabled', True),
            'in_app_enabled': serializer.validated_data.get('in_app_enabled', True),
        }
        
        settings.save()
        
        return Response({
            'message': f'Preferences updated for {notification_type.name}',
            'settings': NotificationSettingsSerializer(settings, context={'request': request}).data
        })


class BulkNotificationActionView(APIView):
    """Perform bulk actions on notifications"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = BulkNotificationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        notification_ids = serializer.validated_data['notification_ids']
        action = serializer.validated_data['action']
        
        # Get user's notifications
        notifications = Notification.objects.filter(
            id__in=notification_ids,
            recipient=request.user
        )
        
        if not notifications.exists():
            return Response({
                'error': 'No valid notifications found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        updated_count = 0
        
        if action == 'mark_read':
            for notification in notifications:
                if not notification.is_read:
                    notification.mark_as_read()
                    updated_count += 1
        
        elif action == 'mark_unread':
            updated_count = notifications.filter(status='read').update(
                status='delivered',
                read_at=None
            )
        
        elif action == 'delete':
            updated_count = notifications.update(
                status='read',
                read_at=timezone.now()
            )
        
        return Response({
            'message': f'Successfully {action.replace("_", " ")} {updated_count} notifications',
            'updated_count': updated_count
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_stats(request):
    """Get notification statistics for current user"""
    user = request.user
    
    # Basic counts
    total_notifications = Notification.objects.filter(
        recipient=user,
        in_app_sent=True
    ).count()
    
    unread_count = Notification.objects.filter(
        recipient=user,
        in_app_sent=True
    ).exclude(status='read').count()
    
    high_priority_count = Notification.objects.filter(
        recipient=user,
        in_app_sent=True,
        priority=1
    ).exclude(status='read').count()
    
    # Recent notifications
    recent_notifications = Notification.objects.filter(
        recipient=user,
        in_app_sent=True
    ).select_related('notification_type', 'sender').order_by('-created_at')[:10]
    
    # Notifications by type
    notifications_by_type = {}
    type_counts = Notification.objects.filter(
        recipient=user,
        in_app_sent=True
    ).values('notification_type__name').annotate(count=Count('id'))
    
    for item in type_counts:
        notifications_by_type[item['notification_type__name']] = item['count']
    
    # Delivery statistics
    delivery_stats = {
        'total_sent': Notification.objects.filter(recipient=user).count(),
        'email_sent': Notification.objects.filter(recipient=user, email_sent=True).count(),
        'push_sent': Notification.objects.filter(recipient=user, push_sent=True).count(),
        'in_app_sent': Notification.objects.filter(recipient=user, in_app_sent=True).count(),
    }
    
    stats_data = {
        'total_notifications': total_notifications,
        'unread_count': unread_count,
        'high_priority_count': high_priority_count,
        'recent_notifications': NotificationListSerializer(
            recent_notifications, many=True, context={'request': request}
        ).data,
        'notifications_by_type': notifications_by_type,
        'delivery_stats': delivery_stats
    }
    
    serializer = NotificationStatsSerializer(stats_data)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_read(request):
    """Mark all notifications as read"""
    user = request.user
    
    unread_notifications = Notification.objects.filter(
        recipient=user,
        in_app_sent=True
    ).exclude(status='read')
    
    updated_count = 0
    for notification in unread_notifications:
        notification.mark_as_read()
        updated_count += 1
    
    return Response({
        'message': f'Marked {updated_count} notifications as read',
        'updated_count': updated_count
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_count(request):
    """Get unread notification count"""
    user = request.user
    
    count = Notification.objects.filter(
        recipient=user,
        in_app_sent=True
    ).exclude(status='read').count()
    
    return Response({
        'unread_count': count
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_notification(request):
    """Send a test notification to current user"""
    user = request.user
    
    from .utils import create_notification
    
    # Get or create test notification type
    test_type, created = NotificationType.objects.get_or_create(
        name='test_notification',
        defaults={
            'description': 'Test notification',
            'icon': '🧪',
            'color': '#17a2b8',
            'priority': 2
        }
    )
    
    notification = create_notification(
        recipient=user,
        notification_type=test_type,
        title='Test Notification',
        message='This is a test notification to verify your notification settings are working correctly.',
        sender=user,
        priority=2
    )
    
    if notification:
        return Response({
            'message': 'Test notification sent successfully',
            'notification': NotificationSerializer(notification, context={'request': request}).data
        })
    else:
        return Response({
            'error': 'Failed to send test notification'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
