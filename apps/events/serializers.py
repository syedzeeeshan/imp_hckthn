"""
Event serializers for Campus Club Management Suite
Seamless API serialization for events, registrations, and resources
"""
from rest_framework import serializers
from django.utils import timezone
from django.db.models import Avg, Count
from apps.authentication.serializers import UserSerializer
from apps.clubs.serializers import ClubListSerializer
from .models import (
    Event, EventCategory, EventRegistration, 
    EventResource, EventFeedback
)

class EventCategorySerializer(serializers.ModelSerializer):
    """Serializer for EventCategory model"""
    
    total_events = serializers.ReadOnlyField()
    
    class Meta:
        model = EventCategory
        fields = [
            'id', 'name', 'description', 'icon', 'color',
            'is_active', 'total_events', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'total_events']


class EventResourceSerializer(serializers.ModelSerializer):
    """Serializer for EventResource model"""
    
    uploaded_by = UserSerializer(read_only=True)
    file_size = serializers.SerializerMethodField()
    can_access = serializers.SerializerMethodField()
    
    class Meta:
        model = EventResource
        fields = [
            'id', 'title', 'description', 'resource_type', 'file',
            'external_url', 'is_public', 'requires_registration',
            'uploaded_by', 'download_count', 'file_size', 'can_access',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'uploaded_by', 'download_count', 'file_size',
            'can_access', 'created_at', 'updated_at'
        ]
    
    def get_file_size(self, obj):
        """Get file size in human readable format"""
        if obj.file:
            try:
                size = obj.file.size
                if size < 1024:
                    return f"{size} B"
                elif size < 1024 * 1024:
                    return f"{size / 1024:.1f} KB"
                elif size < 1024 * 1024 * 1024:
                    return f"{size / (1024 * 1024):.1f} MB"
                else:
                    return f"{size / (1024 * 1024 * 1024):.1f} GB"
            except Exception:
                return None
        return None
    
    def get_can_access(self, obj):
        """Check if current user can access this resource"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.can_user_access(request.user)
        return obj.is_public


class EventFeedbackSerializer(serializers.ModelSerializer):
    """Serializer for EventFeedback model"""
    
    user = UserSerializer(read_only=True)
    user_name = serializers.SerializerMethodField()
    
    class Meta:
        model = EventFeedback
        fields = [
            'id', 'user', 'user_name', 'overall_rating', 'content_rating',
            'organization_rating', 'venue_rating', 'comment', 'suggestions',
            'would_recommend', 'would_attend_again', 'additional_feedback',
            'is_anonymous', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'user_name', 'created_at']
    
    def get_user_name(self, obj):
        """Get user name or anonymous"""
        if obj.is_anonymous:
            return "Anonymous"
        return obj.user.full_name


class EventRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for EventRegistration model"""
    
    user = UserSerializer(read_only=True)
    event_title = serializers.CharField(source='event.title', read_only=True)
    checked_in_by = UserSerializer(read_only=True)
    can_check_in = serializers.SerializerMethodField()
    
    class Meta:
        model = EventRegistration
        fields = [
            'id', 'user', 'event_title', 'status', 'registration_data',
            'payment_status', 'amount_paid', 'checked_in_at', 'checked_in_by',
            'check_in_method', 'feedback_rating', 'feedback_comment',
            'feedback_submitted_at', 'can_check_in', 'created_at'
        ]
        read_only_fields = [
            'id', 'user', 'event_title', 'checked_in_at', 'checked_in_by',
            'check_in_method', 'feedback_submitted_at', 'can_check_in', 'created_at'
        ]
    
    def get_can_check_in(self, obj):
        """Check if registration can be checked in"""
        return obj.status == 'registered' and obj.event.is_ongoing


class EventListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for event listings"""
    
    category = EventCategorySerializer(read_only=True)
    club = ClubListSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    
    # Status properties
    is_upcoming = serializers.ReadOnlyField()
    is_ongoing = serializers.ReadOnlyField()
    is_past = serializers.ReadOnlyField()
    is_full = serializers.ReadOnlyField()
    available_spots = serializers.ReadOnlyField()
    registration_open = serializers.ReadOnlyField()
    duration_hours = serializers.ReadOnlyField()
    attendance_rate = serializers.ReadOnlyField()
    
    # User-specific fields
    user_registered = serializers.SerializerMethodField()
    can_register = serializers.SerializerMethodField()
    
    class Meta:
        model = Event
        fields = [
            'id', 'title', 'slug', 'short_description', 'event_type',
            'category', 'club', 'created_by', 'start_datetime', 'end_datetime',
            'location', 'is_online', 'featured_image', 'max_attendees',
            'registration_required', 'registration_fee', 'status', 'privacy',
            'total_registrations', 'total_attendees', 'is_upcoming',
            'is_ongoing', 'is_past', 'is_full', 'available_spots',
            'registration_open', 'duration_hours', 'attendance_rate',
            'user_registered', 'can_register', 'created_at'
        ]
    
    def get_user_registered(self, obj):
        """Check if current user is registered"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.registrations.filter(
                user=request.user, 
                status__in=['registered', 'attended']
            ).exists()
        return False
    
    def get_can_register(self, obj):
        """Check if current user can register"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.can_user_register(request.user)
        return False


class EventDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for event details"""
    
    category = EventCategorySerializer(read_only=True)
    category_id = serializers.UUIDField(write_only=True, required=False)
    club = ClubListSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    
    # Status properties
    is_upcoming = serializers.ReadOnlyField()
    is_ongoing = serializers.ReadOnlyField()
    is_past = serializers.ReadOnlyField()
    is_full = serializers.ReadOnlyField()
    available_spots = serializers.ReadOnlyField()
    registration_open = serializers.ReadOnlyField()
    duration_hours = serializers.ReadOnlyField()
    attendance_rate = serializers.ReadOnlyField()
    
    # Related data
    resources = EventResourceSerializer(source='resource_files', many=True, read_only=True)
    recent_feedback = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    feedback_count = serializers.SerializerMethodField()
    
    # User-specific fields
    user_registration = serializers.SerializerMethodField()
    can_register = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()
    
    class Meta:
        model = Event
        fields = [
            'id', 'title', 'slug', 'description', 'short_description',
            'event_type', 'category', 'category_id', 'club', 'created_by',
            'start_datetime', 'end_datetime', 'registration_deadline',
            'location', 'venue_details', 'is_online', 'meeting_link',
            'featured_image', 'qr_code', 'max_attendees', 'registration_required',
            'registration_fee', 'status', 'privacy', 'requires_approval',
            'agenda', 'speakers', 'sponsors', 'tags', 'resources_list',
            'external_links', 'total_registrations', 'total_attendees',
            'total_revenue', 'is_upcoming', 'is_ongoing', 'is_past',
            'is_full', 'available_spots', 'registration_open', 'duration_hours',
            'attendance_rate', 'resources', 'recent_feedback', 'average_rating',
            'feedback_count', 'user_registration', 'can_register', 'can_manage',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'slug', 'club', 'created_by', 'qr_code', 'total_registrations',
            'total_attendees', 'total_revenue', 'is_upcoming', 'is_ongoing',
            'is_past', 'is_full', 'available_spots', 'registration_open',
            'duration_hours', 'attendance_rate', 'resources', 'recent_feedback',
            'average_rating', 'feedback_count', 'user_registration', 'can_register',
            'can_manage', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'resources': {'source': 'resources'}  # Rename field
        }
    
    def get_recent_feedback(self, obj):
        """Get recent feedback for this event"""
        feedback = obj.feedback_entries.filter(
            is_approved=True
        ).select_related('user').order_by('-created_at')[:5]
        
        return EventFeedbackSerializer(feedback, many=True, context=self.context).data
    
    def get_average_rating(self, obj):
        """Get average rating for this event"""
        avg = obj.feedback_entries.filter(is_approved=True).aggregate(
            avg_rating=Avg('overall_rating')
        )['avg_rating']
        return round(avg, 1) if avg else None
    
    def get_feedback_count(self, obj):
        """Get total feedback count"""
        return obj.feedback_entries.filter(is_approved=True).count()
    
    def get_user_registration(self, obj):
        """Get current user's registration"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            registration = obj.registrations.filter(user=request.user).first()
            if registration:
                return EventRegistrationSerializer(registration, context=self.context).data
        return None
    
    def get_can_register(self, obj):
        """Check if current user can register"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.can_user_register(request.user)
        return False
    
    def get_can_manage(self, obj):
        """Check if current user can manage this event"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        user = request.user
        return (
            (hasattr(user, 'is_super_admin') and user.is_super_admin) or
            (hasattr(user, 'is_college_admin') and user.is_college_admin) or
            obj.created_by == user or
            obj.club.memberships.filter(
                user=user, 
                status='active', 
                role__in=['admin', 'leader']
            ).exists()
        )
    
    def validate_start_datetime(self, value):
        """Validate start datetime is in the future for new events"""
        if not self.instance and value <= timezone.now():
            raise serializers.ValidationError("Start time must be in the future.")
        return value
    
    def validate(self, attrs):
        """Cross-field validation"""
        start_datetime = attrs.get('start_datetime', getattr(self.instance, 'start_datetime', None))
        end_datetime = attrs.get('end_datetime', getattr(self.instance, 'end_datetime', None))
        registration_deadline = attrs.get('registration_deadline')
        
        if start_datetime and end_datetime:
            if end_datetime <= start_datetime:
                raise serializers.ValidationError("End time must be after start time.")
        
        if registration_deadline and start_datetime:
            if registration_deadline >= start_datetime:
                raise serializers.ValidationError("Registration deadline must be before event start time.")
        
        return attrs


class EventCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating events"""
    
    category_id = serializers.UUIDField(required=False)
    
    class Meta:
        model = Event
        fields = [
            'title', 'description', 'short_description', 'event_type',
            'category_id', 'start_datetime', 'end_datetime', 'registration_deadline',
            'location', 'venue_details', 'is_online', 'meeting_link',
            'featured_image', 'max_attendees', 'registration_required',
            'registration_fee', 'privacy', 'requires_approval', 'agenda',
            'speakers', 'sponsors', 'tags', 'resources', 'external_links'
        ]
    
    def validate_category_id(self, value):
        """Validate category exists and is active"""
        if value:
            try:
                category = EventCategory.objects.get(id=value, is_active=True)
                return value
            except EventCategory.DoesNotExist:
                raise serializers.ValidationError("Invalid category selected.")
        return value
    
    def validate_start_datetime(self, value):
        """Validate start datetime is in the future"""
        if value <= timezone.now():
            raise serializers.ValidationError("Start time must be in the future.")
        return value
    
    def validate(self, attrs):
        """Cross-field validation"""
        start_datetime = attrs.get('start_datetime')
        end_datetime = attrs.get('end_datetime')
        registration_deadline = attrs.get('registration_deadline')
        
        if end_datetime <= start_datetime:
            raise serializers.ValidationError("End time must be after start time.")
        
        if registration_deadline and registration_deadline >= start_datetime:
            raise serializers.ValidationError("Registration deadline must be before event start time.")
        
        return attrs
    
    def create(self, validated_data):
        """Create event with proper setup"""
        request = self.context.get('request')
        club_slug = self.context.get('club_slug')
        
        # Get club
        from apps.clubs.models import Club
        try:
            club = Club.objects.get(slug=club_slug, is_active=True)
        except Club.DoesNotExist:
            raise serializers.ValidationError("Club not found.")
        
        # Set category if provided
        category_id = validated_data.pop('category_id', None)
        category = None
        if category_id:
            try:
                category = EventCategory.objects.get(id=category_id, is_active=True)
            except EventCategory.DoesNotExist:
                raise serializers.ValidationError("Invalid category.")
        
        # Create event
        event = Event.objects.create(
            category=category,
            club=club,
            created_by=request.user,
            status='draft',  # Start as draft
            **validated_data
        )
        
        return event


class EventRegistrationCreateSerializer(serializers.Serializer):
    """Serializer for event registration"""
    
    registration_data = serializers.JSONField(default=dict, required=False)
    
    def validate(self, attrs):
        """Validate user can register for event"""
        request = self.context.get('request')
        event = self.context.get('event')
        
        if not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")
        
        if not event.can_user_register(request.user):
            raise serializers.ValidationError("You cannot register for this event.")
        
        return attrs
    
    def create(self, validated_data):
        """Create event registration"""
        request = self.context.get('request')
        event = self.context.get('event')
        
        # Determine registration status
        status = 'waitlisted' if event.is_full else 'registered'
        
        registration = EventRegistration.objects.create(
            user=request.user,
            event=event,
            status=status,
            registration_data=validated_data.get('registration_data', {}),
            amount_paid=event.registration_fee,
            payment_status='completed' if event.registration_fee == 0 else 'pending'
        )
        
        return registration


class EventFeedbackCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating event feedback"""
    
    class Meta:
        model = EventFeedback
        fields = [
            'overall_rating', 'content_rating', 'organization_rating',
            'venue_rating', 'comment', 'suggestions', 'would_recommend',
            'would_attend_again', 'additional_feedback', 'is_anonymous'
        ]
    
    def validate_overall_rating(self, value):
        """Validate overall rating is required"""
        if not value:
            raise serializers.ValidationError("Overall rating is required.")
        return value
    
    def create(self, validated_data):
        """Create event feedback"""
        request = self.context.get('request')
        event = self.context.get('event')
        
        # Check if user attended the event
        registration = event.registrations.filter(
            user=request.user,
            status='attended'
        ).first()
        
        if not registration:
            raise serializers.ValidationError("You must attend the event to provide feedback.")
        
        feedback = EventFeedback.objects.create(
            event=event,
            user=request.user,
            registration=registration,
            **validated_data
        )
        
        return feedback


class BulkCheckInSerializer(serializers.Serializer):
    """Serializer for bulk check-in operations"""
    
    registration_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=100
    )
    
    def validate_registration_ids(self, value):
        """Validate all registration IDs exist and can be checked in"""
        event = self.context.get('event')
        
        registrations = EventRegistration.objects.filter(
            id__in=value,
            event=event,
            status='registered'
        )
        
        if len(registrations) != len(value):
            raise serializers.ValidationError("Some registration IDs are invalid or cannot be checked in.")
        
        return value
    
    def create(self, validated_data):
        """Perform bulk check-in"""
        event = self.context.get('event')
        request = self.context.get('request')
        registration_ids = validated_data['registration_ids']
        
        registrations = EventRegistration.objects.filter(
            id__in=registration_ids,
            event=event,
            status='registered'
        )
        
        checked_in_count = 0
        for registration in registrations:
            if registration.check_in(checked_in_by=request.user, method='bulk'):
                checked_in_count += 1
        
        return {
            'checked_in_count': checked_in_count,
            'total_requested': len(registration_ids)
        }


class QRCheckInSerializer(serializers.Serializer):
    """Serializer for QR code check-in"""
    
    qr_data = serializers.CharField(max_length=200)
    
    def validate_qr_data(self, value):
        """Validate QR code data format"""
        if not value.startswith('event:'):
            raise serializers.ValidationError("Invalid QR code format.")
        
        try:
            parts = value.split(':')
            if len(parts) != 3:
                raise serializers.ValidationError("Invalid QR code format.")
            
            event_id = parts[1]
            event_slug = parts[2]
            
            # Validate against current event
            event = self.context.get('event')
            if str(event.id) != event_id or event.slug != event_slug:
                raise serializers.ValidationError("QR code does not match this event.")
                
        except Exception:
            raise serializers.ValidationError("Invalid QR code data.")
        
        return value
