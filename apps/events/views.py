"""
Event views for Campus Club Management Suite
Seamless API endpoints for complete event management
"""
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.core.mail import send_mail
from django.conf import settings
import csv
import json

from .models import (
    Event, EventCategory, EventRegistration, 
    EventResource, EventFeedback
)
from .serializers import (
    EventDetailSerializer, EventListSerializer, EventCreateSerializer,
    EventCategorySerializer, EventRegistrationSerializer, EventResourceSerializer,
    EventFeedbackSerializer, EventRegistrationCreateSerializer, EventFeedbackCreateSerializer,
    BulkCheckInSerializer, QRCheckInSerializer
)
from apps.clubs.models import Club


class EventCategoryListView(generics.ListCreateAPIView):
    """List and create event categories"""
    
    queryset = EventCategory.objects.filter(is_active=True).order_by('name')
    serializer_class = EventCategorySerializer
    
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


class EventListView(generics.ListAPIView):
    """List events with comprehensive filtering"""
    
    serializer_class = EventListSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = Event.objects.filter(
            is_active=True, 
            status='published'
        ).select_related(
            'category', 'club', 'club__college', 'created_by'
        ).prefetch_related('registrations')
        
        # Apply filters
        category = self.request.query_params.get('category')
        club = self.request.query_params.get('club')
        college = self.request.query_params.get('college')
        event_type = self.request.query_params.get('type')
        privacy = self.request.query_params.get('privacy')
        search = self.request.query_params.get('search')
        time_filter = self.request.query_params.get('time', 'upcoming')
        
        # Time-based filtering
        now = timezone.now()
        if time_filter == 'upcoming':
            queryset = queryset.filter(start_datetime__gt=now)
        elif time_filter == 'ongoing':
            queryset = queryset.filter(start_datetime__lte=now, end_datetime__gte=now)
        elif time_filter == 'past':
            queryset = queryset.filter(end_datetime__lt=now)
        elif time_filter == 'today':
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start.replace(hour=23, minute=59, second=59, microsecond=999999)
            queryset = queryset.filter(start_datetime__range=(today_start, today_end))
        elif time_filter == 'this_week':
            week_start = now - timezone.timedelta(days=now.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = week_start + timezone.timedelta(days=6, hours=23, minutes=59, seconds=59)
            queryset = queryset.filter(start_datetime__range=(week_start, week_end))
        
        # Category filter
        if category:
            try:
                from uuid import UUID
                category_uuid = UUID(category)
                queryset = queryset.filter(category_id=category_uuid)
            except (ValueError, TypeError):
                queryset = queryset.filter(category__name__icontains=category)
        
        # Club filter
        if club:
            try:
                from uuid import UUID
                club_uuid = UUID(club)
                queryset = queryset.filter(club_id=club_uuid)
            except (ValueError, TypeError):
                queryset = queryset.filter(club__slug=club)
        
        # College filter
        if college:
            queryset = queryset.filter(club__college__name__icontains=college)
        
        # Event type filter
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        # Privacy filter
        if privacy:
            queryset = queryset.filter(privacy=privacy)
        
        # Search filter
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(short_description__icontains=search) |
                Q(location__icontains=search) |
                Q(club__name__icontains=search)
            )
        
        # Ordering
        ordering = self.request.query_params.get('ordering', 'start_datetime')
        valid_orderings = ['start_datetime', '-start_datetime', 'title', '-title', 'created_at', '-created_at']
        if ordering in valid_orderings:
            queryset = queryset.order_by(ordering)
        
        return queryset.distinct()


class EventDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Event detail view with update and delete"""
    
    serializer_class = EventDetailSerializer
    lookup_field = 'slug'
    
    def get_queryset(self):
        return Event.objects.filter(is_active=True).select_related(
            'category', 'club', 'club__college', 'created_by'
        ).prefetch_related(
            'registrations__user', 'resource_files__uploaded_by', 'feedback_entries__user'
        )
    
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def update(self, request, *args, **kwargs):
        event = self.get_object()
        user = request.user
        
        # Check permissions
        can_edit = (
            user.is_authenticated and (
                (hasattr(user, 'is_super_admin') and user.is_super_admin) or
                (hasattr(user, 'is_college_admin') and user.is_college_admin) or
                event.created_by == user or
                event.club.memberships.filter(
                    user=user, status='active', role__in=['admin', 'leader']
                ).exists()
            )
        )
        
        if not can_edit:
            return Response({
                'error': 'You do not have permission to edit this event'
            }, status=status.HTTP_403_FORBIDDEN)
        
        return super().update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        event = self.get_object()
        user = request.user
        
        # Only event creators and super admins can delete
        can_delete = (
            user.is_authenticated and (
                (hasattr(user, 'is_super_admin') and user.is_super_admin) or
                event.created_by == user
            )
        )
        
        if not can_delete:
            return Response({
                'error': 'You do not have permission to delete this event'
            }, status=status.HTTP_403_FORBIDDEN)
        
        return super().destroy(request, *args, **kwargs)


class ClubEventsView(generics.ListCreateAPIView):
    """List and create events for a specific club"""
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return EventCreateSerializer
        return EventListSerializer
    
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return [AllowAny()]
    
    def get_queryset(self):
        club_slug = self.kwargs.get('club_slug')
        try:
            club = Club.objects.get(slug=club_slug, is_active=True)
        except Club.DoesNotExist:
            return Event.objects.none()
        
        queryset = club.events.filter(is_active=True)
        
        # Filter by status based on user permissions
        user = self.request.user
        if not user.is_authenticated or not club.memberships.filter(user=user, status='active').exists():
            queryset = queryset.filter(status='published')
        
        return queryset.select_related('category', 'created_by').order_by('-start_datetime')
    
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
            raise PermissionDenied("You do not have permission to create events for this club")
        
        serializer.save(club=club, created_by=user)


class EventRegistrationView(APIView):
    """Register for an event"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, slug):
        try:
            event = Event.objects.get(slug=slug, is_active=True, status='published')
        except Event.DoesNotExist:
            return Response({
                'error': 'Event not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if already registered
        existing_registration = EventRegistration.objects.filter(
            user=request.user, event=event
        ).first()
        
        if existing_registration:
            return Response({
                'error': f'You are already {existing_registration.status} for this event',
                'registration': EventRegistrationSerializer(existing_registration).data
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create registration
        serializer = EventRegistrationCreateSerializer(
            data=request.data, 
            context={'request': request, 'event': event}
        )
        serializer.is_valid(raise_exception=True)
        registration = serializer.save()
        
        return Response({
            'message': f'Successfully registered for {event.title}',
            'registration': EventRegistrationSerializer(registration).data
        }, status=status.HTTP_201_CREATED)


class EventUnregisterView(APIView):
    """Unregister from an event"""
    
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, slug):
        try:
            event = Event.objects.get(slug=slug, is_active=True)
        except Event.DoesNotExist:
            return Response({
                'error': 'Event not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        try:
            registration = EventRegistration.objects.get(
                user=request.user, 
                event=event, 
                status__in=['registered', 'waitlisted']
            )
        except EventRegistration.DoesNotExist:
            return Response({
                'error': 'You are not registered for this event'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if cancellation is allowed
        if event.start_datetime <= timezone.now():
            return Response({
                'error': 'Cannot unregister after event has started'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        registration.cancel_registration()
        
        return Response({
            'message': f'Successfully unregistered from {event.title}'
        }, status=status.HTTP_200_OK)


class EventAttendeesView(generics.ListAPIView):
    """List event attendees"""
    
    serializer_class = EventRegistrationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        slug = self.kwargs.get('slug')
        try:
            event = Event.objects.get(slug=slug, is_active=True)
        except Event.DoesNotExist:
            return EventRegistration.objects.none()
        
        # Check permissions
        user = self.request.user
        can_view = (
            (hasattr(user, 'is_super_admin') and user.is_super_admin) or
            (hasattr(user, 'is_college_admin') and user.is_college_admin) or
            event.created_by == user or
            event.club.memberships.filter(user=user, status='active', role__in=['admin', 'leader']).exists()
        )
        
        if not can_view:
            # Regular users can only see their own registration
            return event.registrations.filter(user=user).select_related('user')
        
        # Admins can see all registrations
        status_filter = self.request.query_params.get('status', 'all')
        queryset = event.registrations.select_related('user', 'checked_in_by')
        
        if status_filter != 'all':
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('created_at')


class EventCheckInView(APIView):
    """Check-in user to event"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, slug, registration_id):
        try:
            event = Event.objects.get(slug=slug, is_active=True)
        except Event.DoesNotExist:
            return Response({
                'error': 'Event not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check permissions
        user = request.user
        can_checkin = (
            (hasattr(user, 'is_super_admin') and user.is_super_admin) or
            (hasattr(user, 'is_college_admin') and user.is_college_admin) or
            event.created_by == user or
            event.club.memberships.filter(user=user, status='active', role__in=['admin', 'leader']).exists()
        )
        
        if not can_checkin:
            return Response({
                'error': 'You do not have permission to check-in attendees'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            from uuid import UUID
            registration_uuid = UUID(registration_id)
            registration = EventRegistration.objects.get(id=registration_uuid, event=event)
        except (ValueError, EventRegistration.DoesNotExist):
            return Response({
                'error': 'Registration not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if registration.check_in(checked_in_by=user, method='manual'):
            return Response({
                'message': f'Successfully checked in {registration.user.full_name}',
                'registration': EventRegistrationSerializer(registration).data
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Unable to check in user. Registration may not be in correct status.'
            }, status=status.HTTP_400_BAD_REQUEST)


class EventQRCheckInView(APIView):
    """QR code check-in for events"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, slug):
        try:
            event = Event.objects.get(slug=slug, is_active=True)
        except Event.DoesNotExist:
            return Response({
                'error': 'Event not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = QRCheckInSerializer(data=request.data, context={'event': event})
        serializer.is_valid(raise_exception=True)
        
        # Try to find and check in the user
        try:
            registration = EventRegistration.objects.get(
                user=request.user, 
                event=event, 
                status='registered'
            )
            
            if registration.check_in(checked_in_by=request.user, method='qr_code'):
                return Response({
                    'message': f'Successfully checked in to {event.title}',
                    'registration': EventRegistrationSerializer(registration).data
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Unable to check in. Please contact event organizers.'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except EventRegistration.DoesNotExist:
            return Response({
                'error': 'You are not registered for this event'
            }, status=status.HTTP_400_BAD_REQUEST)


class EventBulkCheckInView(APIView):
    """Bulk check-in for events"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, slug):
        try:
            event = Event.objects.get(slug=slug, is_active=True)
        except Event.DoesNotExist:
            return Response({
                'error': 'Event not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check permissions
        user = request.user
        can_checkin = (
            (hasattr(user, 'is_super_admin') and user.is_super_admin) or
            (hasattr(user, 'is_college_admin') and user.is_college_admin) or
            event.created_by == user or
            event.club.memberships.filter(user=user, status='active', role__in=['admin', 'leader']).exists()
        )
        
        if not can_checkin:
            return Response({
                'error': 'You do not have permission to perform bulk check-in'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = BulkCheckInSerializer(
            data=request.data, 
            context={'event': event, 'request': request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        
        return Response({
            'message': f'Bulk check-in completed: {result["checked_in_count"]} out of {result["total_requested"]} attendees',
            **result
        }, status=status.HTTP_200_OK)


class EventFeedbackView(generics.ListCreateAPIView):
    """Event feedback and reviews"""
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return EventFeedbackCreateSerializer
        return EventFeedbackSerializer
    
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return [AllowAny()]
    
    def get_queryset(self):
        slug = self.kwargs.get('slug')
        try:
            event = Event.objects.get(slug=slug, is_active=True)
        except Event.DoesNotExist:
            return EventFeedback.objects.none()
        
        return event.feedback_entries.filter(
            is_approved=True
        ).select_related('user').order_by('-created_at')
    
    def perform_create(self, serializer):
        slug = self.kwargs.get('slug')
        event = get_object_or_404(Event, slug=slug, is_active=True)
        
        serializer.save(event=event, user=self.request.user)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_events(request):
    """Get current user's events"""
    user = request.user
    
    # Get registered events
    registrations = EventRegistration.objects.filter(
        user=user,
        status__in=['registered', 'attended']
    ).select_related('event__club', 'event__category').order_by('-event__start_datetime')
    
    events_data = []
    for registration in registrations:
        event = registration.event
        event_data = EventListSerializer(event, context={'request': request}).data
        event_data['my_status'] = registration.status
        event_data['registration_date'] = registration.created_at
        event_data['checked_in'] = registration.checked_in_at is not None
        events_data.append(event_data)
    
    return Response({
        'events': events_data,
        'total': len(events_data)
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def event_stats(request, slug):
    """Get event statistics"""
    try:
        event = Event.objects.get(slug=slug, is_active=True)
    except Event.DoesNotExist:
        return Response({
            'error': 'Event not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Basic stats
    stats = {
        'total_registrations': event.total_registrations,
        'total_attendees': event.total_attendees,
        'attendance_rate': event.attendance_rate,
        'available_spots': event.available_spots,
        'is_full': event.is_full,
        'total_revenue': float(event.total_revenue),
        'registration_open': event.registration_open,
    }
    
    # Detailed stats for managers
    user = request.user
    if user.is_authenticated:
        can_view_details = (
            (hasattr(user, 'is_super_admin') and user.is_super_admin) or
            (hasattr(user, 'is_college_admin') and user.is_college_admin) or
            event.created_by == user or
            event.club.memberships.filter(user=user, status='active', role__in=['admin', 'leader']).exists()
        )
        
        if can_view_details:
            # Registration status breakdown
            status_breakdown = event.registrations.values('status').annotate(count=Count('id'))
            stats['status_breakdown'] = list(status_breakdown)
            
            # Feedback summary
            feedback_summary = event.feedback_entries.filter(is_approved=True).aggregate(
                avg_rating=Avg('overall_rating'),
                total_feedback=Count('id')
            )
            stats['feedback_summary'] = feedback_summary
            
            # Daily registration trend (last 30 days)
            from datetime import datetime, timedelta
            thirty_days_ago = timezone.now() - timedelta(days=30)
            daily_registrations = event.registrations.filter(
                created_at__gte=thirty_days_ago
            ).extra(
                select={'day': 'date(created_at)'}
            ).values('day').annotate(count=Count('id')).order_by('day')
            stats['daily_registrations'] = list(daily_registrations)
    
    return Response(stats)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_attendees(request, slug):
    """Export event attendees as CSV"""
    try:
        event = Event.objects.get(slug=slug, is_active=True)
    except Event.DoesNotExist:
        return Response({
            'error': 'Event not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check permissions
    user = request.user
    can_export = (
        (hasattr(user, 'is_super_admin') and user.is_super_admin) or
        (hasattr(user, 'is_college_admin') and user.is_college_admin) or
        event.created_by == user or
        event.club.memberships.filter(user=user, status='active', role__in=['admin', 'leader']).exists()
    )
    
    if not can_export:
        return Response({
            'error': 'You do not have permission to export attendees'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{event.slug}_attendees.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Name', 'Email', 'Status', 'Registration Date', 
        'Check-in Time', 'Amount Paid', 'Feedback Rating'
    ])
    
    registrations = event.registrations.select_related('user').order_by('created_at')
    
    for registration in registrations:
        writer.writerow([
            registration.user.full_name,
            registration.user.email,
            registration.status,
            registration.created_at.strftime('%Y-%m-%d %H:%M'),
            registration.checked_in_at.strftime('%Y-%m-%d %H:%M') if registration.checked_in_at else '',
            str(registration.amount_paid),
            registration.feedback_rating or ''
        ])
    
    return response


@api_view(['GET'])
@permission_classes([AllowAny])
def search_events(request):
    """Advanced event search"""
    query = request.GET.get('q', '').strip()
    location = request.GET.get('location')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if not any([query, location, date_from, date_to]):
        return Response({
            'results': [],
            'total': 0
        })
    
    queryset = Event.objects.filter(is_active=True, status='published')
    
    if query:
        queryset = queryset.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(short_description__icontains=query) |
            Q(club__name__icontains=query)
        )
    
    if location:
        queryset = queryset.filter(
            Q(location__icontains=location) |
            Q(venue_details__icontains=location)
        )
    
    if date_from:
        try:
            from datetime import datetime
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            queryset = queryset.filter(start_datetime__date__gte=date_from_parsed)
        except ValueError:
            pass
    
    if date_to:
        try:
            from datetime import datetime
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            queryset = queryset.filter(start_datetime__date__lte=date_to_parsed)
        except ValueError:
            pass
    
    events = queryset.select_related('category', 'club', 'created_by')[:20]
    serializer = EventListSerializer(events, many=True, context={'request': request})
    
    return Response({
        'results': serializer.data,
        'total': queryset.count()
    })
