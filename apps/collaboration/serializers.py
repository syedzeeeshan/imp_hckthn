"""
Collaboration serializers for Campus Club Management Suite
Seamless API serialization for inter-college partnerships and projects
"""
from rest_framework import serializers
from django.utils import timezone
from django.db.models import Avg, Count
from apps.authentication.serializers import UserSerializer
from apps.clubs.serializers import ClubListSerializer
from .models import (
    Collaboration, CollaborationType, CollaborationParticipation,
    CollaborationMilestone, CollaborationMessage, CollaborationResource
)

class CollaborationTypeSerializer(serializers.ModelSerializer):
    """Serializer for CollaborationType model"""
    
    total_collaborations = serializers.ReadOnlyField()
    
    class Meta:
        model = CollaborationType
        fields = [
            'id', 'name', 'description', 'icon', 'color', 'is_active',
            'min_participants', 'max_participants', 'requires_approval',
            'total_collaborations', 'created_at'
        ]
        read_only_fields = ['id', 'total_collaborations', 'created_at']


class CollaborationResourceSerializer(serializers.ModelSerializer):
    """Serializer for CollaborationResource model"""
    
    uploaded_by = UserSerializer(read_only=True)
    file_size = serializers.SerializerMethodField()
    can_access = serializers.SerializerMethodField()
    
    class Meta:
        model = CollaborationResource
        fields = [
            'id', 'title', 'description', 'resource_type', 'file',
            'external_url', 'is_public', 'uploaded_by', 'download_count',
            'file_size', 'can_access', 'created_at', 'updated_at'
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


class CollaborationMilestoneSerializer(serializers.ModelSerializer):
    """Serializer for CollaborationMilestone model"""
    
    assigned_clubs = ClubListSerializer(many=True, read_only=True)
    assigned_by = UserSerializer(read_only=True)
    completed_by = UserSerializer(read_only=True)
    is_overdue = serializers.ReadOnlyField()
    days_until_due = serializers.SerializerMethodField()
    
    class Meta:
        model = CollaborationMilestone
        fields = [
            'id', 'title', 'description', 'due_date', 'assigned_clubs',
            'assigned_by', 'status', 'progress_percentage', 'completed_at',
            'completed_by', 'deliverables', 'attachments', 'is_overdue',
            'days_until_due', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'assigned_clubs', 'assigned_by', 'completed_at',
            'completed_by', 'is_overdue', 'days_until_due',
            'created_at', 'updated_at'
        ]
    
    def get_days_until_due(self, obj):
        """Get days until due date"""
        if obj.status in ['completed', 'cancelled']:
            return None
        
        days = (obj.due_date - timezone.now().date()).days
        return days


class CollaborationMessageSerializer(serializers.ModelSerializer):
    """Serializer for CollaborationMessage model"""
    
    sender = UserSerializer(read_only=True)
    sender_club = serializers.SerializerMethodField()
    replies_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CollaborationMessage
        fields = [
            'id', 'sender', 'sender_club', 'message_type', 'subject',
            'content', 'attachments', 'parent_message', 'is_announcement',
            'is_pinned', 'replies_count', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'sender', 'sender_club', 'replies_count',
            'created_at', 'updated_at'
        ]
    
    def get_sender_club(self, obj):
        """Get sender's club in this collaboration"""
        user_participation = obj.collaboration.participations.filter(
            club__memberships__user=obj.sender,
            club__memberships__status='active',
            status__in=['approved', 'active', 'completed']
        ).first()
        
        if user_participation:
            return ClubListSerializer(user_participation.club).data
        return None
    
    def get_replies_count(self, obj):
        """Get number of replies to this message"""
        return obj.replies.count()


class CollaborationParticipationSerializer(serializers.ModelSerializer):
    """Serializer for CollaborationParticipation model"""
    
    club = ClubListSerializer(read_only=True)
    primary_contact = UserSerializer(read_only=True)
    approved_by = UserSerializer(read_only=True)
    collaboration_title = serializers.CharField(source='collaboration.title', read_only=True)
    
    class Meta:
        model = CollaborationParticipation
        fields = [
            'id', 'club', 'collaboration_title', 'status', 'role',
            'application_message', 'committed_members', 'committed_hours_per_week',
            'committed_resources', 'primary_contact', 'joined_at', 'approved_by',
            'contribution_score', 'tasks_completed', 'milestones_achieved',
            'final_rating', 'feedback', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'club', 'collaboration_title', 'primary_contact',
            'joined_at', 'approved_by', 'contribution_score',
            'tasks_completed', 'milestones_achieved', 'created_at', 'updated_at'
        ]


class CollaborationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for collaboration listings"""
    
    collaboration_type = CollaborationTypeSerializer(read_only=True)
    initiator_club = ClubListSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    project_lead = UserSerializer(read_only=True)
    
    # Status properties
    is_open_for_applications = serializers.ReadOnlyField()
    is_full = serializers.ReadOnlyField()
    available_spots = serializers.ReadOnlyField()
    duration_days = serializers.ReadOnlyField()
    is_upcoming = serializers.ReadOnlyField()
    is_ongoing = serializers.ReadOnlyField()
    is_past = serializers.ReadOnlyField()
    
    # User-specific fields
    user_club_status = serializers.SerializerMethodField()
    can_apply = serializers.SerializerMethodField()
    
    class Meta:
        model = Collaboration
        fields = [
            'id', 'title', 'slug', 'short_description', 'collaboration_type',
            'initiator_club', 'created_by', 'project_lead', 'start_date',
            'end_date', 'application_deadline', 'max_participants',
            'min_participants', 'total_participants', 'total_applications',
            'status', 'priority', 'privacy', 'progress_percentage',
            'featured_image', 'tags', 'is_open_for_applications', 'is_full',
            'available_spots', 'duration_days', 'is_upcoming', 'is_ongoing',
            'is_past', 'user_club_status', 'can_apply', 'created_at'
        ]
    
    def get_user_club_status(self, obj):
        """Get current user's club participation status"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            user_clubs = request.user.joined_clubs.filter(
                memberships__status='active'
            )
            
            for club in user_clubs:
                status = obj.get_participation_status(club)
                if status:
                    return {
                        'club': ClubListSerializer(club).data,
                        'status': status
                    }
        return None
    
    def get_can_apply(self, obj):
        """Check if current user's club can apply"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            user_clubs = request.user.joined_clubs.filter(
                memberships__status='active',
                memberships__role__in=['admin', 'leader']  # Only leaders can apply
            )
            
            for club in user_clubs:
                if obj.can_club_apply(club):
                    return True
        return False


class CollaborationDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for collaboration details"""
    
    collaboration_type = CollaborationTypeSerializer(read_only=True)
    collaboration_type_id = serializers.UUIDField(write_only=True, required=False)
    initiator_club = ClubListSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    project_lead = UserSerializer(read_only=True)
    project_lead_id = serializers.UUIDField(write_only=True, required=False)
    
    # Status properties
    is_open_for_applications = serializers.ReadOnlyField()
    is_full = serializers.ReadOnlyField()
    available_spots = serializers.ReadOnlyField()
    duration_days = serializers.ReadOnlyField()
    is_upcoming = serializers.ReadOnlyField()
    is_ongoing = serializers.ReadOnlyField()
    is_past = serializers.ReadOnlyField()
    
    # Related data
    participations = CollaborationParticipationSerializer(many=True, read_only=True)
    milestones = CollaborationMilestoneSerializer(source='milestone_objects', many=True, read_only=True)
    recent_messages = serializers.SerializerMethodField()
    resources = CollaborationResourceSerializer(source='shared_resources', many=True, read_only=True)
    
    # Statistics
    participation_stats = serializers.SerializerMethodField()
    
    # User-specific fields
    user_club_status = serializers.SerializerMethodField()
    can_apply = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()
    
    class Meta:
        model = Collaboration
        fields = [
            'id', 'title', 'slug', 'description', 'short_description',
            'collaboration_type', 'collaboration_type_id', 'tags',
            'initiator_club', 'created_by', 'project_lead', 'project_lead_id',
            'start_date', 'end_date', 'application_deadline', 'max_participants',
            'min_participants', 'total_participants', 'total_applications',
            'objectives', 'deliverables', 'requirements', 'skills_needed',
            'budget', 'resources_needed', 'resources_provided', 'status',
            'priority', 'privacy', 'allows_external_participants',
            'progress_percentage', 'milestones_list', 'communication_channels',
            'meeting_schedule', 'featured_image', 'documents', 'success_rating',
            'is_open_for_applications', 'is_full', 'available_spots',
            'duration_days', 'is_upcoming', 'is_ongoing', 'is_past',
            'participations', 'milestones', 'recent_messages', 'resources',
            'participation_stats', 'user_club_status', 'can_apply',
            'can_manage', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'slug', 'initiator_club', 'created_by', 'total_participants',
            'total_applications', 'success_rating', 'is_open_for_applications',
            'is_full', 'available_spots', 'duration_days', 'is_upcoming',
            'is_ongoing', 'is_past', 'participations', 'milestones',
            'recent_messages', 'resources', 'participation_stats',
            'user_club_status', 'can_apply', 'can_manage', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'milestones_list': {'source': 'milestones'}
        }
    
    def get_recent_messages(self, obj):
        """Get recent messages for this collaboration"""
        messages = obj.messages.select_related('sender').order_by('-created_at')[:10]
        return CollaborationMessageSerializer(messages, many=True, context=self.context).data
    
    def get_participation_stats(self, obj):
        """Get participation statistics"""
        participations = obj.participations.all()
        
        status_counts = {}
        for participation in participations:
            status = participation.status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        role_counts = {}
        for participation in participations.filter(status__in=['approved', 'active', 'completed']):
            role = participation.role
            role_counts[role] = role_counts.get(role, 0) + 1
        
        return {
            'status_distribution': status_counts,
            'role_distribution': role_counts,
            'avg_contribution_score': participations.filter(
                status__in=['active', 'completed']
            ).aggregate(avg=Avg('contribution_score'))['avg'] or 0
        }
    
    def get_user_club_status(self, obj):
        """Get current user's club participation status"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            user_clubs = request.user.joined_clubs.filter(
                memberships__status='active'
            )
            
            for club in user_clubs:
                participation = obj.participations.filter(club=club).first()
                if participation:
                    return CollaborationParticipationSerializer(participation, context=self.context).data
        return None
    
    def get_can_apply(self, obj):
        """Check if current user's club can apply"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            user_clubs = request.user.joined_clubs.filter(
                memberships__status='active',
                memberships__role__in=['admin', 'leader']
            )
            
            for club in user_clubs:
                if obj.can_club_apply(club):
                    return True
        return False
    
    def get_can_manage(self, obj):
        """Check if current user can manage this collaboration"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        user = request.user
        return (
            (hasattr(user, 'is_super_admin') and user.is_super_admin) or
            (hasattr(user, 'is_college_admin') and user.is_college_admin) or
            obj.created_by == user or
            obj.project_lead == user or
            obj.initiator_club.memberships.filter(
                user=user, 
                status='active',
                role__in=['admin', 'leader']
            ).exists()
        )
    
    def validate_start_date(self, value):
        """Validate start date is in the future"""
        if not self.instance and value <= timezone.now().date():
            raise serializers.ValidationError("Start date must be in the future.")
        return value
    
    def validate(self, attrs):
        """Cross-field validation"""
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        application_deadline = attrs.get('application_deadline')
        min_participants = attrs.get('min_participants', getattr(self.instance, 'min_participants', 2))
        max_participants = attrs.get('max_participants', getattr(self.instance, 'max_participants', 10))
        
        if start_date and end_date:
            if end_date <= start_date:
                raise serializers.ValidationError("End date must be after start date.")
        
        if application_deadline and start_date:
            if application_deadline.date() >= start_date:
                raise serializers.ValidationError("Application deadline must be before start date.")
        
        if max_participants < min_participants:
            raise serializers.ValidationError("Maximum participants cannot be less than minimum participants.")
        
        return attrs


class CollaborationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating collaborations"""
    
    collaboration_type_id = serializers.UUIDField(required=False)
    project_lead_id = serializers.UUIDField(required=False)
    
    class Meta:
        model = Collaboration
        fields = [
            'title', 'description', 'short_description', 'collaboration_type_id',
            'tags', 'project_lead_id', 'start_date', 'end_date',
            'application_deadline', 'max_participants', 'min_participants',
            'objectives', 'deliverables', 'requirements', 'skills_needed',
            'budget', 'resources_needed', 'resources_provided', 'privacy',
            'priority', 'allows_external_participants', 'communication_channels',
            'meeting_schedule', 'featured_image', 'documents'
        ]
    
    def validate_collaboration_type_id(self, value):
        """Validate collaboration type exists"""
        if value:
            try:
                collaboration_type = CollaborationType.objects.get(id=value, is_active=True)
                return value
            except CollaborationType.DoesNotExist:
                raise serializers.ValidationError("Invalid collaboration type selected.")
        return value
    
    def validate_project_lead_id(self, value):
        """Validate project lead exists and has permissions"""
        if value:
            try:
                from apps.authentication.models import User
                user = User.objects.get(id=value, is_active=True)
                # Additional validation can be added here
                return value
            except User.DoesNotExist:
                raise serializers.ValidationError("Invalid project lead selected.")
        return value
    
    def create(self, validated_data):
        """Create collaboration with proper setup"""
        request = self.context.get('request')
        club = self.context.get('club')
        
        # Set collaboration type if provided
        collaboration_type_id = validated_data.pop('collaboration_type_id', None)
        collaboration_type = None
        if collaboration_type_id:
            try:
                collaboration_type = CollaborationType.objects.get(
                    id=collaboration_type_id, is_active=True
                )
            except CollaborationType.DoesNotExist:
                raise serializers.ValidationError("Invalid collaboration type.")
        
        # Set project lead if provided
        project_lead_id = validated_data.pop('project_lead_id', None)
        project_lead = None
        if project_lead_id:
            try:
                from apps.authentication.models import User
                project_lead = User.objects.get(id=project_lead_id, is_active=True)
            except User.DoesNotExist:
                raise serializers.ValidationError("Invalid project lead.")
        
        # Create collaboration
        collaboration = Collaboration.objects.create(
            collaboration_type=collaboration_type,
            initiator_club=club,
            created_by=request.user,
            project_lead=project_lead or request.user,
            status='draft',
            **validated_data
        )
        
        return collaboration


class CollaborationApplicationSerializer(serializers.Serializer):
    """Serializer for club collaboration applications"""
    
    application_message = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    committed_members = serializers.IntegerField(min_value=1, default=1)
    committed_hours_per_week = serializers.IntegerField(min_value=1, default=5)
    committed_resources = serializers.ListField(
        child=serializers.CharField(max_length=200),
        required=False,
        allow_empty=True
    )
    role = serializers.ChoiceField(
        choices=CollaborationParticipation.ROLE_CHOICES,
        default='participant'
    )
    primary_contact_id = serializers.UUIDField(required=False)
    
    def validate_primary_contact_id(self, value):
        """Validate primary contact is a member of the applying club"""
        if value:
            club = self.context.get('club')
            try:
                from apps.authentication.models import User
                contact = User.objects.get(id=value, is_active=True)
                
                # Check if contact is a member of the club
                if not club.memberships.filter(user=contact, status='active').exists():
                    raise serializers.ValidationError(
                        "Primary contact must be a member of your club."
                    )
                
                return value
            except User.DoesNotExist:
                raise serializers.ValidationError("Invalid primary contact selected.")
        return value
    
    def validate(self, attrs):
        """Validate application details"""
        collaboration = self.context.get('collaboration')
        club = self.context.get('club')
        
        if not collaboration.can_club_apply(club):
            raise serializers.ValidationError(
                "Your club cannot apply for this collaboration."
            )
        
        return attrs
