"""
Notifications serializers for Campus Club Management Suite
Seamless API serialization for notification system
"""
from rest_framework import serializers
from django.utils import timezone
from apps.authentication.serializers import UserSerializer
from .models import (
    NotificationType, NotificationSettings, Notification,
    NotificationBatch, PushNotificationDevice
)

class NotificationTypeSerializer(serializers.ModelSerializer):
    """Serializer for NotificationType model"""
    
    class Meta:
        model = NotificationType
        fields = [
            'id', 'name', 'description', 'icon', 'color', 'default_enabled',
            'default_email_enabled', 'default_push_enabled', 'default_in_app_enabled',
            'priority', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class NotificationSettingsSerializer(serializers.ModelSerializer):
    """Serializer for NotificationSettings model"""
    
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = NotificationSettings
        fields = [
            'id', 'user', 'notifications_enabled', 'email_notifications_enabled',
            'push_notifications_enabled', 'in_app_notifications_enabled',
            'email_frequency', 'quiet_hours_enabled', 'quiet_hours_start',
            'quiet_hours_end', 'type_settings', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
    
    def validate(self, attrs):
        """Validate quiet hours"""
        quiet_hours_enabled = attrs.get('quiet_hours_enabled', False)
        quiet_hours_start = attrs.get('quiet_hours_start')
        quiet_hours_end = attrs.get('quiet_hours_end')
        
        if quiet_hours_enabled:
            if not quiet_hours_start or not quiet_hours_end:
                raise serializers.ValidationError(
                    "Both quiet_hours_start and quiet_hours_end are required when quiet hours are enabled"
                )
        
        return attrs


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model"""
    
    recipient = UserSerializer(read_only=True)
    sender = UserSerializer(read_only=True)
    notification_type = NotificationTypeSerializer(read_only=True)
    time_since_created = serializers.ReadOnlyField()
    is_read = serializers.ReadOnlyField()
    related_object = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'recipient', 'sender', 'notification_type', 'title', 'message',
            'action_url', 'related_object_type', 'related_object_id', 'related_object',
            'data', 'priority', 'status', 'send_email', 'send_push', 'send_in_app',
            'scheduled_at', 'sent_at', 'delivered_at', 'read_at', 'expires_at',
            'email_sent', 'push_sent', 'in_app_sent', 'error_message',
            'time_since_created', 'is_read', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'recipient', 'sender', 'notification_type', 'status',
            'sent_at', 'delivered_at', 'read_at', 'email_sent', 'push_sent',
            'in_app_sent', 'error_message', 'time_since_created', 'is_read',
            'related_object', 'created_at', 'updated_at'
        ]
    
    def get_related_object(self, obj):
        """Get related object details"""
        related_obj = obj.get_related_object()
        if related_obj:
            # Return basic info about the related object
            return {
                'type': obj.related_object_type,
                'id': str(obj.related_object_id),
                'title': getattr(related_obj, 'title', getattr(related_obj, 'name', str(related_obj)))
            }
        return None


class NotificationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for notification lists"""
    
    notification_type = NotificationTypeSerializer(read_only=True)
    sender = UserSerializer(read_only=True)
    time_since_created = serializers.ReadOnlyField()
    is_read = serializers.ReadOnlyField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'sender', 'title', 'message',
            'action_url', 'priority', 'status', 'time_since_created',
            'is_read', 'created_at'
        ]


class NotificationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating notifications"""
    
    recipient_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=True
    )
    notification_type_id = serializers.UUIDField(write_only=True, required=True)
    
    class Meta:
        model = Notification
        fields = [
            'recipient_ids', 'notification_type_id', 'title', 'message',
            'action_url', 'related_object_type', 'related_object_id',
            'data', 'priority', 'send_email', 'send_push', 'send_in_app',
            'scheduled_at', 'expires_at'
        ]
    
    def validate_recipient_ids(self, value):
        """Validate recipient IDs"""
        if not value:
            raise serializers.ValidationError("At least one recipient is required")
        
        from apps.authentication.models import User
        existing_users = User.objects.filter(id__in=value, is_active=True)
        if len(existing_users) != len(value):
            raise serializers.ValidationError("One or more recipients not found")
        
        return value
    
    def validate_notification_type_id(self, value):
        """Validate notification type"""
        try:
            notification_type = NotificationType.objects.get(id=value, is_active=True)
            return value
        except NotificationType.DoesNotExist:
            raise serializers.ValidationError("Invalid notification type")
    
    def create(self, validated_data):
        """Create notifications for all recipients"""
        recipient_ids = validated_data.pop('recipient_ids')
        notification_type_id = validated_data.pop('notification_type_id')
        sender = self.context['request'].user
        
        from apps.authentication.models import User
        from .utils import create_notification
        
        notification_type = NotificationType.objects.get(id=notification_type_id)
        notifications = []
        
        for recipient_id in recipient_ids:
            recipient = User.objects.get(id=recipient_id)
            notification = create_notification(
                recipient=recipient,
                notification_type=notification_type,
                sender=sender,
                **validated_data
            )
            if notification:
                notifications.append(notification)
        
        return notifications[0] if notifications else None


class NotificationBatchSerializer(serializers.ModelSerializer):
    """Serializer for NotificationBatch model"""
    
    created_by = UserSerializer(read_only=True)
    notification_type = NotificationTypeSerializer(read_only=True)
    recipients = UserSerializer(many=True, read_only=True)
    
    class Meta:
        model = NotificationBatch
        fields = [
            'id', 'name', 'description', 'recipients', 'title_template',
            'message_template', 'notification_type', 'scheduled_at', 'priority',
            'status', 'send_email', 'send_push', 'send_in_app', 'total_recipients',
            'sent_count', 'failed_count', 'created_by', 'created_at', 'sent_at'
        ]
        read_only_fields = [
            'id', 'recipients', 'notification_type', 'status', 'total_recipients',
            'sent_count', 'failed_count', 'created_by', 'created_at', 'sent_at'
        ]


class PushNotificationDeviceSerializer(serializers.ModelSerializer):
    """Serializer for PushNotificationDevice model"""
    
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = PushNotificationDevice
        fields = [
            'id', 'user', 'device_type', 'device_token', 'device_name',
            'is_active', 'last_used_at', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'last_used_at', 'created_at']
    
    def create(self, validated_data):
        """Create or update device token"""
        user = self.context['request'].user
        device_token = validated_data['device_token']
        
        # Update existing device or create new one
        device, created = PushNotificationDevice.objects.update_or_create(
            user=user,
            device_token=device_token,
            defaults=validated_data
        )
        
        return device


class NotificationStatsSerializer(serializers.Serializer):
    """Serializer for notification statistics"""
    
    total_notifications = serializers.IntegerField()
    unread_count = serializers.IntegerField()
    high_priority_count = serializers.IntegerField()
    recent_notifications = NotificationListSerializer(many=True)
    notifications_by_type = serializers.DictField()
    delivery_stats = serializers.DictField()


class NotificationPreferencesSerializer(serializers.Serializer):
    """Serializer for updating notification preferences"""
    
    notification_type_id = serializers.UUIDField()
    enabled = serializers.BooleanField()
    email_enabled = serializers.BooleanField(required=False)
    push_enabled = serializers.BooleanField(required=False)
    in_app_enabled = serializers.BooleanField(required=False)
    
    def validate_notification_type_id(self, value):
        """Validate notification type exists"""
        try:
            NotificationType.objects.get(id=value, is_active=True)
            return value
        except NotificationType.DoesNotExist:
            raise serializers.ValidationError("Invalid notification type")


class BulkNotificationActionSerializer(serializers.Serializer):
    """Serializer for bulk notification actions"""
    
    notification_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True
    )
    action = serializers.ChoiceField(
        choices=['mark_read', 'mark_unread', 'delete'],
        required=True
    )
    
    def validate_notification_ids(self, value):
        """Validate notification IDs"""
        if not value:
            raise serializers.ValidationError("At least one notification ID is required")
        
        if len(value) > 100:  # Limit bulk operations
            raise serializers.ValidationError("Cannot process more than 100 notifications at once")
        
        return value
