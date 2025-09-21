"""
Collaboration views for Campus Club Management Suite
Seamless API endpoints for inter-college partnerships and project management
"""
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from .models import (
    Collaboration, CollaborationType, CollaborationParticipation,
    CollaborationMilestone, CollaborationMessage, CollaborationResource
)
from .serializers import (
    CollaborationDetailSerializer, CollaborationListSerializer,
    CollaborationCreateSerializer, CollaborationTypeSerializer,
    CollaborationParticipationSerializer, CollaborationMilestoneSerializer,
    CollaborationMessageSerializer, CollaborationResourceSerializer,
    CollaborationApplicationSerializer
)
from apps.clubs.models import Club


class CollaborationTypeListView(generics.ListCreateAPIView):
    """List and create collaboration types"""
    
    queryset = CollaborationType.objects.filter(is_active=True).order_by('name')
    serializer_class = CollaborationTypeSerializer
    
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return [AllowAny()]
    
    def perform_create(self, serializer):
        # Only super admins can create types
        if not (hasattr(self.request.user, 'is_super_admin') and self.request.user.is_super_admin):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only super admins can create collaboration types")
        serializer.save()


class CollaborationListView(generics.ListAPIView):
    """List collaborations with comprehensive filtering"""
    
    serializer_class = CollaborationListSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = Collaboration.objects.filter(
            is_active=True
        ).select_related(
            'collaboration_type', 'initiator_club', 'created_by', 'project_lead'
        ).prefetch_related('participations__club')
        
        # Apply filters
        collaboration_type = self.request.query_params.get('type')
        status_filter = self.request.query_params.get('status')
        priority = self.request.query_params.get('priority')
        privacy = self.request.query_params.get('privacy')
        search = self.request.query_params.get('search')
        college = self.request.query_params.get('college')
        time_filter = self.request.query_params.get('time', 'all')
        
        # Status filtering (public collaborations for non-authenticated users)
        user = self.request.user
        if not user.is_authenticated:
            queryset = queryset.filter(status='open', privacy='public')
        else:
            # Authenticated users see more based on permissions
            if not (hasattr(user, 'is_super_admin') and user.is_super_admin):
                user_clubs = user.joined_clubs.filter(memberships__status='active')
                queryset = queryset.filter(
                    Q(privacy='public') |
                    Q(privacy='college_network', initiator_club__college__domain=user.college_email_domain) |
                    Q(initiator_club__in=user_clubs) |
                    Q(participations__club__in=user_clubs)
                ).distinct()
        
        # Time-based filtering
        now = timezone.now().date()
        if time_filter == 'upcoming':
            queryset = queryset.filter(start_date__gt=now)
        elif time_filter == 'ongoing':
            queryset = queryset.filter(start_date__lte=now, end_date__gte=now)
        elif time_filter == 'completed':
            queryset = queryset.filter(end_date__lt=now, status='completed')
        elif time_filter == 'open':
            queryset = queryset.filter(status='open')
        
        # Other filters
        if collaboration_type:
            try:
                from uuid import UUID
                type_uuid = UUID(collaboration_type)
                queryset = queryset.filter(collaboration_type_id=type_uuid)
            except (ValueError, TypeError):
                queryset = queryset.filter(collaboration_type__name__icontains=collaboration_type)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if priority:
            queryset = queryset.filter(priority=priority)
        
        if privacy:
            queryset = queryset.filter(privacy=privacy)
        
        if college:
            queryset = queryset.filter(initiator_club__college__name__icontains=college)
        
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(short_description__icontains=search) |
                Q(tags__icontains=search)
            )
        
        # Ordering
        ordering = self.request.query_params.get('ordering', '-created_at')
        valid_orderings = [
            'start_date', '-start_date', 'title', '-title',
            'created_at', '-created_at', 'priority', '-priority'
        ]
        if ordering in valid_orderings:
            queryset = queryset.order_by(ordering)
        
        return queryset


class CollaborationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Collaboration detail view with update and delete"""
    
    serializer_class = CollaborationDetailSerializer
    lookup_field = 'slug'
    
    def get_queryset(self):
        return Collaboration.objects.filter(is_active=True).select_related(
            'collaboration_type', 'initiator_club', 'created_by', 'project_lead'
        ).prefetch_related(
            'participations__club', 'milestone_objects', 'messages__sender',
            'shared_resources__uploaded_by'
        )
    
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def update(self, request, *args, **kwargs):
        collaboration = self.get_object()
        user = request.user
        
        # Check permissions
        can_edit = (
            user.is_authenticated and (
                (hasattr(user, 'is_super_admin') and user.is_super_admin) or
                (hasattr(user, 'is_college_admin') and user.is_college_admin) or
                collaboration.created_by == user or
                collaboration.project_lead == user or
                collaboration.initiator_club.memberships.filter(
                    user=user, status='active', role__in=['admin', 'leader']
                ).exists()
            )
        )
        
        if not can_edit:
            return Response({
                'error': 'You do not have permission to edit this collaboration'
            }, status=status.HTTP_403_FORBIDDEN)
        
        return super().update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        collaboration = self.get_object()
        user = request.user
        
        # Only creators and super admins can delete
        can_delete = (
            user.is_authenticated and (
                (hasattr(user, 'is_super_admin') and user.is_super_admin) or
                collaboration.created_by == user
            )
        )
        
        if not can_delete:
            return Response({
                'error': 'You do not have permission to delete this collaboration'
            }, status=status.HTTP_403_FORBIDDEN)
        
        return super().destroy(request, *args, **kwargs)


class ClubCollaborationsView(generics.ListCreateAPIView):
    """List and create collaborations for a specific club"""
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CollaborationCreateSerializer
        return CollaborationListSerializer
    
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return [AllowAny()]
    
    def get_queryset(self):
        club_slug = self.kwargs.get('club_slug')
        try:
            club = Club.objects.get(slug=club_slug, is_active=True)
        except Club.DoesNotExist:
            return Collaboration.objects.none()
        
        # Get collaborations where club is initiator or participant
        queryset = Collaboration.objects.filter(
            Q(initiator_club=club) |
            Q(participations__club=club, participations__status__in=['approved', 'active', 'completed']),
            is_active=True
        ).select_related('collaboration_type', 'created_by').distinct()
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        club_slug = self.kwargs.get('club_slug')
        club = get_object_or_404(Club, slug=club_slug, is_active=True)
        
        # Check permissions
        user = self.request.user
        can_create = (
            (hasattr(user, 'is_super_admin') and user.is_super_admin) or
            (hasattr(user, 'is_college_admin') and user.is_college_admin) or
            club.memberships.filter(user=user, status='active', role__in=['admin', 'leader']).exists()
        )
        
        if not can_create:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not have permission to create collaborations for this club")
        
        serializer.save(club=club)


class CollaborationApplicationView(APIView):
    """Apply for collaboration participation"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, slug, club_slug):
        try:
            collaboration = Collaboration.objects.get(slug=slug, is_active=True)
            club = Club.objects.get(slug=club_slug, is_active=True)
        except (Collaboration.DoesNotExist, Club.DoesNotExist):
            return Response({
                'error': 'Collaboration or club not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user can apply for this club
        user = request.user
        can_apply = club.memberships.filter(
            user=user, 
            status='active', 
            role__in=['admin', 'leader']
        ).exists()
        
        if not can_apply:
            return Response({
                'error': 'You must be a club leader or admin to apply for collaborations'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Check if already applied
        existing_participation = CollaborationParticipation.objects.filter(
            collaboration=collaboration, club=club
        ).first()
        
        if existing_participation:
            return Response({
                'error': f'Your club has already applied (Status: {existing_participation.status})'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create application
        serializer = CollaborationApplicationSerializer(
            data=request.data,
            context={'collaboration': collaboration, 'club': club}
        )
        serializer.is_valid(raise_exception=True)
        
        # Set primary contact
        primary_contact_id = serializer.validated_data.get('primary_contact_id')
        if primary_contact_id:
            from apps.authentication.models import User
            primary_contact = User.objects.get(id=primary_contact_id)
        else:
            primary_contact = user
        
        participation = CollaborationParticipation.objects.create(
            collaboration=collaboration,
            club=club,
            primary_contact=primary_contact,
            **serializer.validated_data
        )
        
        # Send notification to collaboration owner
        self._send_application_notification(collaboration, club, user)
        
        return Response({
            'message': f'Successfully applied for {collaboration.title}',
            'participation': CollaborationParticipationSerializer(participation).data
        }, status=status.HTTP_201_CREATED)
    
    def _send_application_notification(self, collaboration, club, applicant):
        """Send notification about new application"""
        try:
            send_mail(
                subject=f'New collaboration application: {collaboration.title}',
                message=f'''Hello,

{club.name} has applied to join your collaboration "{collaboration.title}".

Application submitted by: {applicant.full_name}
Club: {club.name}

Please review and respond to this application in the collaboration management dashboard.

Best regards,
Campus Club Management Team''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[collaboration.created_by.email],
                fail_silently=True
            )
            
            if collaboration.project_lead and collaboration.project_lead != collaboration.created_by:
                send_mail(
                    subject=f'New collaboration application: {collaboration.title}',
                    message=f'''Hello {collaboration.project_lead.full_name},

{club.name} has applied to join the collaboration "{collaboration.title}" that you are leading.

Please review and respond to this application.

Best regards,
Campus Club Management Team''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[collaboration.project_lead.email],
                    fail_silently=True
                )
        except Exception as e:
            print(f"Failed to send application notification: {e}")


class ManageParticipationView(APIView):
    """Manage collaboration participation (approve, reject, etc.)"""
    
    permission_classes = [IsAuthenticated]
    
    def patch(self, request, slug, participation_id):
        try:
            collaboration = Collaboration.objects.get(slug=slug, is_active=True)
            participation = CollaborationParticipation.objects.get(
                id=participation_id, 
                collaboration=collaboration
            )
        except (Collaboration.DoesNotExist, CollaborationParticipation.DoesNotExist):
            return Response({
                'error': 'Collaboration or participation not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check permissions
        user = request.user
        can_manage = (
            (hasattr(user, 'is_super_admin') and user.is_super_admin) or
            (hasattr(user, 'is_college_admin') and user.is_college_admin) or
            collaboration.created_by == user or
            collaboration.project_lead == user or
            collaboration.initiator_club.memberships.filter(
                user=user, status='active', role__in=['admin', 'leader']
            ).exists()
        )
        
        if not can_manage:
            return Response({
                'error': 'You do not have permission to manage participations'
            }, status=status.HTTP_403_FORBIDDEN)
        
        action = request.data.get('action')
        
        if action == 'approve':
            if participation.approve_participation(user):
                message = f'{participation.club.name} has been approved for participation'
                self._send_approval_notification(participation)
            else:
                return Response({
                    'error': 'Participation cannot be approved'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        elif action == 'reject':
            reason = request.data.get('reason', '')
            if participation.reject_participation(reason):
                message = f'{participation.club.name} participation has been rejected'
                self._send_rejection_notification(participation, reason)
            else:
                return Response({
                    'error': 'Participation cannot be rejected'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        elif action == 'withdraw':
            # Only club members can withdraw their own participation
            if participation.club.memberships.filter(user=user, status='active', role__in=['admin', 'leader']).exists():
                if participation.withdraw_participation():
                    message = f'{participation.club.name} has withdrawn from the collaboration'
                else:
                    return Response({
                        'error': 'Cannot withdraw at this time'
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    'error': 'You can only withdraw your own club\'s participation'
                }, status=status.HTTP_403_FORBIDDEN)
        
        else:
            return Response({
                'error': 'Invalid action'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'message': message,
            'participation': CollaborationParticipationSerializer(participation).data
        }, status=status.HTTP_200_OK)
    
    def _send_approval_notification(self, participation):
        """Send approval notification"""
        try:
            send_mail(
                subject=f'Collaboration application approved: {participation.collaboration.title}',
                message=f'''Congratulations!

Your club {participation.club.name} has been approved to participate in "{participation.collaboration.title}".

You can now access the collaboration workspace and begin contributing to the project.

Best regards,
{participation.collaboration.initiator_club.name} Team''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[participation.primary_contact.email],
                fail_silently=True
            )
        except Exception as e:
            print(f"Failed to send approval notification: {e}")
    
    def _send_rejection_notification(self, participation, reason):
        """Send rejection notification"""
        try:
            send_mail(
                subject=f'Collaboration application update: {participation.collaboration.title}',
                message=f'''Hello,

Thank you for your interest in "{participation.collaboration.title}".

Unfortunately, we cannot accept {participation.club.name} for participation at this time.

{f"Reason: {reason}" if reason else ""}

We encourage you to apply for other collaboration opportunities.

Best regards,
{participation.collaboration.initiator_club.name} Team''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[participation.primary_contact.email],
                fail_silently=True
            )
        except Exception as e:
            print(f"Failed to send rejection notification: {e}")


class CollaborationParticipantsView(generics.ListAPIView):
    """List collaboration participants"""
    
    serializer_class = CollaborationParticipationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        slug = self.kwargs.get('slug')
        try:
            collaboration = Collaboration.objects.get(slug=slug, is_active=True)
        except Collaboration.DoesNotExist:
            return CollaborationParticipation.objects.none()
        
        # Check permissions
        user = self.request.user
        can_view_all = (
            (hasattr(user, 'is_super_admin') and user.is_super_admin) or
            (hasattr(user, 'is_college_admin') and user.is_college_admin) or
            collaboration.created_by == user or
            collaboration.project_lead == user or
            collaboration.initiator_club.memberships.filter(
                user=user, status='active', role__in=['admin', 'leader']
            ).exists()
        )
        
        queryset = collaboration.participations.select_related('club', 'primary_contact', 'approved_by')
        
        if can_view_all:
            # Managers can see all participations
            status_filter = self.request.query_params.get('status')
            if status_filter:
                queryset = queryset.filter(status=status_filter)
        else:
            # Regular users see only approved/active participants and their own applications
            user_clubs = user.joined_clubs.filter(memberships__status='active')
            queryset = queryset.filter(
                Q(status__in=['approved', 'active', 'completed']) |
                Q(club__in=user_clubs)
            )
        
        return queryset.order_by('-created_at')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_collaborations(request):
    """Get current user's collaborations"""
    user = request.user
    
    # Get user's clubs
    user_clubs = user.joined_clubs.filter(memberships__status='active')
    
    # Get collaborations where user's clubs are involved
    collaborations = Collaboration.objects.filter(
        Q(initiator_club__in=user_clubs) |
        Q(participations__club__in=user_clubs, participations__status__in=['approved', 'active', 'completed']),
        is_active=True
    ).select_related('collaboration_type', 'initiator_club').distinct()
    
    collaborations_data = []
    for collaboration in collaborations:
        collab_data = CollaborationListSerializer(collaboration, context={'request': request}).data
        
        # Add user's role in this collaboration
        user_participation = collaboration.participations.filter(
            club__in=user_clubs
        ).first()
        
        if user_participation:
            collab_data['my_participation'] = CollaborationParticipationSerializer(user_participation).data
        elif collaboration.initiator_club in user_clubs:
            collab_data['my_role'] = 'initiator'
        
        collaborations_data.append(collab_data)
    
    return Response({
        'collaborations': collaborations_data,
        'total': len(collaborations_data)
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def collaboration_stats(request, slug):
    """Get collaboration statistics"""
    try:
        collaboration = Collaboration.objects.get(slug=slug, is_active=True)
    except Collaboration.DoesNotExist:
        return Response({
            'error': 'Collaboration not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Basic stats
    stats = {
        'total_participants': collaboration.total_participants,
        'total_applications': collaboration.total_applications,
        'progress_percentage': collaboration.progress_percentage,
        'available_spots': collaboration.available_spots,
        'duration_days': collaboration.duration_days,
        'is_open_for_applications': collaboration.is_open_for_applications,
    }
    
    # Detailed stats for authorized users
    user = request.user
    if user.is_authenticated:
        can_view_details = (
            (hasattr(user, 'is_super_admin') and user.is_super_admin) or
            (hasattr(user, 'is_college_admin') and user.is_college_admin) or
            collaboration.created_by == user or
            collaboration.project_lead == user or
            collaboration.initiator_club.memberships.filter(
                user=user, status='active', role__in=['admin', 'leader']
            ).exists()
        )
        
        if can_view_details:
            # Application status breakdown
            status_breakdown = collaboration.participations.values('status').annotate(count=Count('id'))
            stats['application_status'] = list(status_breakdown)
            
            # Role distribution
            role_breakdown = collaboration.participations.filter(
                status__in=['approved', 'active', 'completed']
            ).values('role').annotate(count=Count('id'))
            stats['role_distribution'] = list(role_breakdown)
            
            # Milestone progress
            total_milestones = collaboration.milestone_objects.count()
            completed_milestones = collaboration.milestone_objects.filter(status='completed').count()
            stats['milestone_progress'] = {
                'total': total_milestones,
                'completed': completed_milestones,
                'percentage': int((completed_milestones / total_milestones) * 100) if total_milestones > 0 else 0
            }
    
    return Response(stats)


@api_view(['GET'])
@permission_classes([AllowAny])
def search_collaborations(request):
    """Advanced collaboration search"""
    query = request.GET.get('q', '').strip()
    collaboration_type = request.GET.get('type')
    college = request.GET.get('college')
    skills = request.GET.get('skills')
    
    if not any([query, collaboration_type, college, skills]):
        return Response({
            'results': [],
            'total': 0
        })
    
    queryset = Collaboration.objects.filter(is_active=True, status='open')
    
    if query:
        queryset = queryset.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(short_description__icontains=query) |
            Q(tags__icontains=query)
        )
    
    if collaboration_type:
        queryset = queryset.filter(collaboration_type__name__icontains=collaboration_type)
    
    if college:
        queryset = queryset.filter(initiator_club__college__name__icontains=college)
    
    if skills:
        skills_list = [skill.strip() for skill in skills.split(',')]
        for skill in skills_list:
            queryset = queryset.filter(skills_needed__icontains=skill)
    
    collaborations = queryset.select_related(
        'collaboration_type', 'initiator_club', 'created_by'
    )[:20]
    
    serializer = CollaborationListSerializer(
        collaborations, 
        many=True, 
        context={'request': request}
    )
    
    return Response({
        'results': serializer.data,
        'total': queryset.count()
    })
