"""
Club serializers for Campus Club Management Suite
API serialization for clubs, memberships, and related models
"""
from rest_framework import serializers
from django.utils import timezone
from apps.authentication.serializers import UserSerializer
from apps.authentication.models import College
from .models import (
    Club, ClubCategory, ClubMembership, 
    ClubSettings, ClubAnnouncement
)

class ClubCategorySerializer(serializers.ModelSerializer):
    """Serializer for ClubCategory model"""
    
    total_clubs = serializers.ReadOnlyField()
    
    class Meta:
        model = ClubCategory
        fields = [
            'id', 'name', 'description', 'icon', 'color',
            'is_active', 'total_clubs', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'total_clubs']


class ClubMembershipSerializer(serializers.ModelSerializer):
    """Serializer for ClubMembership model"""
    
    user = UserSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True, required=False)
    membership_duration = serializers.ReadOnlyField()
    is_leader = serializers.ReadOnlyField()
    
    class Meta:
        model = ClubMembership
        fields = [
            'id', 'user', 'user_id', 'role', 'status', 'joined_at',
            'requested_at', 'events_attended', 'last_activity',
            'membership_duration', 'is_leader', 'created_at'
        ]
        read_only_fields = [
            'id', 'user', 'joined_at', 'requested_at', 'events_attended',
            'last_activity', 'membership_duration', 'is_leader', 'created_at'
        ]


class ClubSettingsSerializer(serializers.ModelSerializer):
    """Serializer for ClubSettings model"""
    
    class Meta:
        model = ClubSettings
        fields = [
            'notify_new_members', 'notify_events', 'notify_collaborations',
            'show_member_list', 'show_contact_info', 'allow_member_invites',
            'auto_approve_events', 'require_event_approval', 'custom_fields',
            'calendar_sync', 'email_integration'
        ]


class ClubAnnouncementSerializer(serializers.ModelSerializer):
    """Serializer for ClubAnnouncement model"""
    
    created_by = UserSerializer(read_only=True)
    is_active = serializers.ReadOnlyField()
    club_name = serializers.CharField(source='club.name', read_only=True)
    
    class Meta:
        model = ClubAnnouncement
        fields = [
            'id', 'title', 'content', 'priority', 'target_all_members',
            'target_roles', 'is_published', 'send_email', 'send_notification',
            'publish_at', 'expires_at', 'views', 'created_by', 'club_name',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'views', 'created_by', 'club_name', 'is_active',
            'created_at', 'updated_at'
        ]


class ClubListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for club listings"""
    
    category = ClubCategorySerializer(read_only=True)
    member_count = serializers.ReadOnlyField()
    leader_count = serializers.ReadOnlyField()
    activity_score = serializers.ReadOnlyField()
    college_name = serializers.CharField(source='college.name', read_only=True)
    
    class Meta:
        model = Club
        fields = [
            'id', 'name', 'slug', 'short_description', 'logo', 'category',
            'college_name', 'status', 'privacy', 'member_count', 'leader_count',
            'activity_score', 'is_verified', 'created_at'
        ]


class ClubDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for club details"""
    
    category = ClubCategorySerializer(read_only=True)
    category_id = serializers.UUIDField(write_only=True, required=False)
    college_name = serializers.CharField(source='college.name', read_only=True)
    created_by = UserSerializer(read_only=True)
    
    # Calculated fields
    member_count = serializers.ReadOnlyField()
    leader_count = serializers.ReadOnlyField()
    pending_requests = serializers.ReadOnlyField()
    is_full = serializers.ReadOnlyField()
    activity_score = serializers.ReadOnlyField()
    social_links = serializers.JSONField()
    
    # Settings
    settings = ClubSettingsSerializer(read_only=True)
    
    # Recent announcements (limited)
    recent_announcements = serializers.SerializerMethodField()
    
    # User-specific fields
    user_membership = serializers.SerializerMethodField()
    can_join = serializers.SerializerMethodField()
    
    class Meta:
        model = Club
        fields = [
            'id', 'name', 'slug', 'description', 'short_description',
            'logo', 'cover_image', 'category', 'category_id', 'college_name',
            'email', 'phone', 'website', 'social_links', 'meeting_location',
            'meeting_schedule', 'meeting_days', 'status', 'privacy',
            'is_verified', 'requires_approval', 'max_members',
            'membership_fee', 'budget', 'total_events', 'total_collaborations',
            'member_count', 'leader_count', 'pending_requests', 'is_full',
            'activity_score', 'created_by', 'settings', 'recent_announcements',
            'user_membership', 'can_join', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'slug', 'college_name', 'total_events', 'total_collaborations',
            'member_count', 'leader_count', 'pending_requests', 'is_full',
            'activity_score', 'created_by', 'settings', 'recent_announcements',
            'user_membership', 'can_join', 'created_at', 'updated_at'
        ]
    
    def get_recent_announcements(self, obj):
        """Get recent announcements for this club"""
        announcements = obj.announcements.filter(
            is_published=True
        ).order_by('-created_at')[:3]
        
        return ClubAnnouncementSerializer(announcements, many=True).data
    
    def get_user_membership(self, obj):
        """Get current user's membership in this club"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            membership = obj.memberships.filter(user=request.user).first()
            if membership:
                return ClubMembershipSerializer(membership).data
        return None
    
    def get_can_join(self, obj):
        """Check if current user can join this club"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.can_user_join(request.user)
        return False
    
    def validate_category_id(self, value):
        """Validate category exists and is active"""
        if value:
            try:
                category = ClubCategory.objects.get(id=value, is_active=True)
                return value
            except ClubCategory.DoesNotExist:
                raise serializers.ValidationError("Invalid category selected.")
        return value
    
    def validate_max_members(self, value):
        """Validate max members is reasonable"""
        if value and value < 1:
            raise serializers.ValidationError("Maximum members must be at least 1.")
        if value and value > 10000:
            raise serializers.ValidationError("Maximum members cannot exceed 10,000.")
        return value
    
    def validate_social_links(self, value):
        """Validate social media links format"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Social links must be a dictionary.")
        
        # Validate URL format for each link
        import re
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        for platform, url in value.items():
            if url and not url_pattern.match(url):
                raise serializers.ValidationError(f"Invalid URL format for {platform}.")
        
        return value


class ClubCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new clubs"""
    
    category_id = serializers.UUIDField(required=True)
    
    class Meta:
        model = Club
        fields = [
            'name', 'description', 'short_description', 'logo', 'cover_image',
            'category_id', 'email', 'phone', 'website', 'social_links',
            'meeting_location', 'meeting_schedule', 'meeting_days',
            'privacy', 'requires_approval', 'max_members', 'membership_fee'
        ]
    
    def validate_name(self, value):
        """Validate club name is unique within college"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            college = getattr(request.user, 'college', None)
            if college and Club.objects.filter(name=value, college=college).exists():
                raise serializers.ValidationError(
                    "A club with this name already exists in your college."
                )
        return value
    
    def validate_category_id(self, value):
        """Validate category exists"""
        try:
            category = ClubCategory.objects.get(id=value, is_active=True)
            return value
        except ClubCategory.DoesNotExist:
            raise serializers.ValidationError("Invalid category selected.")
    
    def create(self, validated_data):
        """Create club with proper setup"""
        request = self.context.get('request')
        user = request.user
        
        # Set category and college
        category_id = validated_data.pop('category_id')
        category = ClubCategory.objects.get(id=category_id)
        
        # Get user's college
        college = College.objects.filter(domain=user.college_email_domain).first()
        if not college:
            raise serializers.ValidationError("Your college is not registered in the system.")
        
        # Create club
        club = Club.objects.create(
            category=category,
            college=college,
            created_by=user,
            status='pending' if not user.is_college_admin else 'active',
            **validated_data
        )
        
        # Make creator a leader
        ClubMembership.objects.create(
            user=user,
            club=club,
            role='admin',
            status='active',
            joined_at=timezone.now(),
            approved_by=user
        )
        
        return club


class JoinClubSerializer(serializers.Serializer):
    """Serializer for joining a club"""
    
    message = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate(self, attrs):
        """Validate user can join the club"""
        request = self.context.get('request')
        club = self.context.get('club')
        
        if not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")
        
        if not club.can_user_join(request.user):
            raise serializers.ValidationError("You cannot join this club.")
        
        return attrs


class ManageMembershipSerializer(serializers.Serializer):
    """Serializer for managing membership (approve/reject/role change)"""
    
    ACTION_CHOICES = [
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('change_role', 'Change Role'),
        ('deactivate', 'Deactivate'),
    ]
    
    action = serializers.ChoiceField(choices=ACTION_CHOICES)
    role = serializers.ChoiceField(choices=ClubMembership.ROLE_CHOICES, required=False)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate(self, attrs):
        """Validate action and required fields"""
        action = attrs.get('action')
        
        if action == 'change_role' and not attrs.get('role'):
            raise serializers.ValidationError("Role is required for role change.")
        
        return attrs
