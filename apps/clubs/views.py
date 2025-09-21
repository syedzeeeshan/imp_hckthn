"""
Club views for Campus Club Management Suite
Error-free API views for club management, membership, and administration
"""
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from .models import (
    Club, ClubCategory, ClubMembership, 
    ClubSettings, ClubAnnouncement
)
from .serializers import (
    ClubDetailSerializer, ClubListSerializer, ClubCreateSerializer,
    ClubCategorySerializer, ClubMembershipSerializer, ClubSettingsSerializer,
    ClubAnnouncementSerializer, JoinClubSerializer, ManageMembershipSerializer
)
from apps.authentication.models import User


class ClubCategoryListView(generics.ListCreateAPIView):
    """List and create club categories"""
    
    queryset = ClubCategory.objects.filter(is_active=True).order_by('name')
    serializer_class = ClubCategorySerializer
    
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return [AllowAny()]
    
    def perform_create(self, serializer):
        # Only super admins can create categories
        if not (hasattr(self.request.user, 'is_super_admin') and self.request.user.is_super_admin):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only super admins can create categories")
        serializer.save()


class ClubListView(generics.ListAPIView):
    """List clubs with filtering and search"""
    
    serializer_class = ClubListSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = Club.objects.filter(is_active=True, status='active').select_related(
            'category', 'college', 'created_by'
        ).prefetch_related('memberships')
        
        # Apply filters
        category = self.request.query_params.get('category')
        college = self.request.query_params.get('college')
        search = self.request.query_params.get('search')
        privacy = self.request.query_params.get('privacy')
        
        if category:
            try:
                from uuid import UUID
                category_uuid = UUID(category)
                queryset = queryset.filter(category_id=category_uuid)
            except (ValueError, TypeError):
                queryset = queryset.filter(category__name__icontains=category)
        
        if college:
            queryset = queryset.filter(college__name__icontains=college)
        
        if privacy:
            queryset = queryset.filter(privacy=privacy)
        
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(short_description__icontains=search)
            )
        
        # Ordering
        ordering = self.request.query_params.get('ordering', '-created_at')
        if ordering in ['name', '-name', 'created_at', '-created_at', 'member_count', '-member_count']:
            if ordering in ['member_count', '-member_count']:
                queryset = queryset.annotate(
                    member_count_annotated=Count('memberships', filter=Q(memberships__status='active'))
                ).order_by(f"{'-' if ordering.startswith('-') else ''}member_count_annotated")
            else:
                queryset = queryset.order_by(ordering)
        
        return queryset.distinct()


class ClubDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Club detail view with update and delete"""
    
    serializer_class = ClubDetailSerializer
    lookup_field = 'slug'
    
    def get_queryset(self):
        return Club.objects.filter(is_active=True).select_related(
            'category', 'college', 'created_by', 'settings'
        ).prefetch_related('memberships__user', 'announcements')
    
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def update(self, request, *args, **kwargs):
        club = self.get_object()
        user = request.user
        
        # Check permissions
        can_edit = (
            user.is_authenticated and (
                (hasattr(user, 'is_super_admin') and user.is_super_admin) or
                (hasattr(user, 'is_college_admin') and user.is_college_admin) or
                club.memberships.filter(user=user, status='active', role__in=['admin', 'leader']).exists()
            )
        )
        
        if not can_edit:
            return Response({
                'error': 'You do not have permission to edit this club'
            }, status=status.HTTP_403_FORBIDDEN)
        
        return super().update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        club = self.get_object()
        user = request.user
        
        # Only super admins and club creators can delete
        can_delete = (
            user.is_authenticated and (
                (hasattr(user, 'is_super_admin') and user.is_super_admin) or
                club.created_by == user
            )
        )
        
        if not can_delete:
            return Response({
                'error': 'You do not have permission to delete this club'
            }, status=status.HTTP_403_FORBIDDEN)
        
        return super().destroy(request, *args, **kwargs)


class ClubCreateView(generics.CreateAPIView):
    """Create new club"""
    
    serializer_class = ClubCreateSerializer
    permission_classes = [IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        # Check if user can create clubs
        user = request.user
        if not hasattr(user, 'user_type'):
            return Response({
                'error': 'User type not found'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Students and club leaders can create clubs
        if user.user_type not in ['student', 'club_leader', 'college_admin', 'super_admin']:
            return Response({
                'error': 'You do not have permission to create clubs'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        club = serializer.save()
        
        # Return detailed club information
        detail_serializer = ClubDetailSerializer(club, context={'request': request})
        
        return Response({
            'message': 'Club created successfully',
            'club': detail_serializer.data
        }, status=status.HTTP_201_CREATED)


class JoinClubView(APIView):
    """Join a club"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, slug):
        try:
            club = Club.objects.get(slug=slug, is_active=True, status='active')
        except Club.DoesNotExist:
            return Response({
                'error': 'Club not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        user = request.user
        
        # Check if already a member
        existing_membership = ClubMembership.objects.filter(user=user, club=club).first()
        if existing_membership:
            if existing_membership.status == 'active':
                return Response({
                    'error': 'You are already a member of this club'
                }, status=status.HTTP_400_BAD_REQUEST)
            elif existing_membership.status == 'pending':
                return Response({
                    'error': 'Your membership request is pending approval'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user can join
        if not club.can_user_join(user):
            return Response({
                'error': 'You cannot join this club'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create membership request
        serializer = JoinClubSerializer(data=request.data, context={'request': request, 'club': club})
        serializer.is_valid(raise_exception=True)
        
        membership_status = 'active' if not club.requires_approval else 'pending'
        joined_at = timezone.now() if not club.requires_approval else None
        
        membership = ClubMembership.objects.create(
            user=user,
            club=club,
            status=membership_status,
            joined_at=joined_at,
            approved_by=user if not club.requires_approval else None
        )
        
        message = 'Successfully joined the club' if not club.requires_approval else 'Membership request submitted for approval'
        
        return Response({
            'message': message,
            'membership': ClubMembershipSerializer(membership).data
        }, status=status.HTTP_201_CREATED)


class LeaveClubView(APIView):
    """Leave a club"""
    
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, slug):
        try:
            club = Club.objects.get(slug=slug, is_active=True)
        except Club.DoesNotExist:
            return Response({
                'error': 'Club not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            membership = ClubMembership.objects.get(user=request.user, club=club, status='active')
        except ClubMembership.DoesNotExist:
            return Response({
                'error': 'You are not a member of this club'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user is the only admin
        if membership.role == 'admin':
            admin_count = club.memberships.filter(status='active', role='admin').count()
            if admin_count == 1:
                return Response({
                    'error': 'You cannot leave as you are the only admin. Please assign another admin first.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        membership.delete()
        
        return Response({
            'message': 'Successfully left the club'
        }, status=status.HTTP_200_OK)


class ClubMembersView(generics.ListAPIView):
    """List club members"""
    
    serializer_class = ClubMembershipSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        slug = self.kwargs.get('slug')
        try:
            club = Club.objects.get(slug=slug, is_active=True)
        except Club.DoesNotExist:
            return ClubMembership.objects.none()
        
        # Check if user can view members
        user = self.request.user
        if not club.settings.show_member_list:
            # Only members and admins can view member list if privacy is enabled
            is_member = club.memberships.filter(user=user, status='active').exists()
            is_admin = (hasattr(user, 'is_college_admin') and user.is_college_admin) or (hasattr(user, 'is_super_admin') and user.is_super_admin)
            if not (is_member or is_admin):
                return ClubMembership.objects.none()
        
        return club.memberships.filter(status='active').select_related('user').order_by('role', 'joined_at')


class ManageMembershipView(APIView):
    """Manage club memberships (approve, reject, change role)"""
    
    permission_classes = [IsAuthenticated]
    
    def patch(self, request, slug, membership_id):
        try:
            club = Club.objects.get(slug=slug, is_active=True)
        except Club.DoesNotExist:
            return Response({
                'error': 'Club not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            from uuid import UUID
            membership_uuid = UUID(membership_id)
            membership = ClubMembership.objects.get(id=membership_uuid, club=club)
        except (ValueError, ClubMembership.DoesNotExist):
            return Response({
                'error': 'Membership not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check permissions
        user = request.user
        can_manage = (
            (hasattr(user, 'is_super_admin') and user.is_super_admin) or
            (hasattr(user, 'is_college_admin') and user.is_college_admin) or
            club.memberships.filter(user=user, status='active', role__in=['admin', 'leader']).exists()
        )
        
        if not can_manage:
            return Response({
                'error': 'You do not have permission to manage memberships'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = ManageMembershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        action = serializer.validated_data['action']
        
        if action == 'approve':
            if membership.status == 'pending':
                membership.approve_membership(user)
                message = 'Membership approved'
            else:
                return Response({
                    'error': 'Membership is not pending approval'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        elif action == 'reject':
            if membership.status == 'pending':
                membership.reject_membership()
                return Response({
                    'message': 'Membership request rejected'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Membership is not pending approval'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        elif action == 'change_role':
            new_role = serializer.validated_data.get('role')
            membership.role = new_role
            membership.save()
            message = f'Role changed to {new_role}'
        
        elif action == 'deactivate':
            membership.status = 'inactive'
            membership.save()
            message = 'Membership deactivated'
        
        return Response({
            'message': message,
            'membership': ClubMembershipSerializer(membership).data
        }, status=status.HTTP_200_OK)


class ClubAnnouncementsView(generics.ListCreateAPIView):
    """Club announcements"""
    
    serializer_class = ClubAnnouncementSerializer
    
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return [AllowAny()]
    
    def get_queryset(self):
        slug = self.kwargs.get('slug')
        try:
            club = Club.objects.get(slug=slug, is_active=True)
        except Club.DoesNotExist:
            return ClubAnnouncement.objects.none()
        
        queryset = club.announcements.filter(is_published=True).select_related('created_by').order_by('-created_at')
        
        # Filter active announcements for non-members
        user = self.request.user
        if not user.is_authenticated or not club.memberships.filter(user=user, status='active').exists():
            now = timezone.now()
            queryset = queryset.filter(
                Q(publish_at__isnull=True) | Q(publish_at__lte=now),
                Q(expires_at__isnull=True) | Q(expires_at__gte=now)
            )
        
        return queryset
    
    def perform_create(self, serializer):
        slug = self.kwargs.get('slug')
        club = get_object_or_404(Club, slug=slug, is_active=True)
        
        # Check permissions
        user = self.request.user
        can_create = (
            (hasattr(user, 'is_super_admin') and user.is_super_admin) or
            (hasattr(user, 'is_college_admin') and user.is_college_admin) or
            club.memberships.filter(user=user, status='active', role__in=['admin', 'leader']).exists()
        )
        
        if not can_create:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not have permission to create announcements")
        
        serializer.save(club=club, created_by=user)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_clubs(request):
    """Get current user's clubs"""
    user = request.user
    memberships = ClubMembership.objects.filter(
        user=user, 
        status='active'
    ).select_related('club__category', 'club__college').order_by('club__name')
    
    clubs_data = []
    for membership in memberships:
        club = membership.club
        club_data = ClubListSerializer(club).data
        club_data['my_role'] = membership.role
        club_data['joined_at'] = membership.joined_at
        clubs_data.append(club_data)
    
    return Response({
        'clubs': clubs_data,
        'total': len(clubs_data)
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def club_stats(request, slug):
    """Get club statistics"""
    try:
        club = Club.objects.get(slug=slug, is_active=True)
    except Club.DoesNotExist:
        return Response({
            'error': 'Club not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Basic stats
    stats = {
        'member_count': club.member_count,
        'leader_count': club.leader_count,
        'pending_requests': club.pending_requests,
        'total_events': club.total_events,
        'total_collaborations': club.total_collaborations,
        'activity_score': club.activity_score,
        'created_at': club.created_at,
        'last_updated': club.updated_at,
    }
    
    # Role distribution (only for members and admins)
    user = request.user
    if user.is_authenticated:
        is_member = club.memberships.filter(user=user, status='active').exists()
        is_admin = (hasattr(user, 'is_college_admin') and user.is_college_admin) or (hasattr(user, 'is_super_admin') and user.is_super_admin)
        
        if is_member or is_admin:
            role_distribution = club.memberships.filter(status='active').values('role').annotate(count=Count('role'))
            stats['role_distribution'] = list(role_distribution)
    
    return Response(stats)


@api_view(['GET'])
@permission_classes([AllowAny])
def search_clubs(request):
    """Advanced club search"""
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category')
    college = request.GET.get('college')
    
    if not query and not category and not college:
        return Response({
            'results': [],
            'total': 0
        })
    
    queryset = Club.objects.filter(is_active=True, status='active')
    
    if query:
        queryset = queryset.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(short_description__icontains=query)
        )
    
    if category:
        queryset = queryset.filter(category__name__icontains=category)
    
    if college:
        queryset = queryset.filter(college__name__icontains=college)
    
    clubs = queryset.select_related('category', 'college')[:20]  # Limit results
    
    serializer = ClubListSerializer(clubs, many=True)
    
    return Response({
        'results': serializer.data,
        'total': queryset.count()
    })
