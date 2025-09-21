"""
Analytics views for Campus Club Management Suite
Comprehensive analytics API endpoints with seamless data access
"""
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from django.http import HttpResponse
from datetime import datetime, timedelta
import csv
import json

from .models import AnalyticsReport, DashboardWidget
from .serializers import (
    AnalyticsReportSerializer, AnalyticsReportCreateSerializer,
    DashboardWidgetSerializer, QuickStatsSerializer, ChartDataSerializer,
    AnalyticsExportSerializer
)
from apps.clubs.models import Club
from apps.events.models import Event, EventRegistration
from apps.authentication.models import User


class AnalyticsReportListView(generics.ListCreateAPIView):
    """List and create analytics reports"""
    
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AnalyticsReportCreateSerializer
        return AnalyticsReportSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = AnalyticsReport.objects.select_related('club', 'college', 'generated_by')
        
        # Filter based on user permissions
        if hasattr(user, 'is_super_admin') and user.is_super_admin:
            pass  # Can see all reports
        elif hasattr(user, 'is_college_admin') and user.is_college_admin:
            queryset = queryset.filter(
                Q(college__domain=user.college_email_domain) |
                Q(generated_by=user) |
                Q(is_public=True)
            )
        else:
            # Regular users see only their reports and public reports
            queryset = queryset.filter(
                Q(generated_by=user) |
                Q(is_public=True)
            )
        
        # Apply filters
        report_type = self.request.query_params.get('type')
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('-created_at')


class AnalyticsReportDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Analytics report detail view"""
    
    serializer_class = AnalyticsReportSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = AnalyticsReport.objects.select_related('club', 'college', 'generated_by')
        
        if hasattr(user, 'is_super_admin') and user.is_super_admin:
            return queryset
        elif hasattr(user, 'is_college_admin') and user.is_college_admin:
            return queryset.filter(
                Q(college__domain=user.college_email_domain) |
                Q(generated_by=user) |
                Q(is_public=True)
            )
        else:
            return queryset.filter(
                Q(generated_by=user) |
                Q(is_public=True)
            )
    
    def update(self, request, *args, **kwargs):
        report = self.get_object()
        
        # Only report creator or super admin can update
        if report.generated_by != request.user and not (hasattr(request.user, 'is_super_admin') and request.user.is_super_admin):
            return Response({
                'error': 'You do not have permission to update this report'
            }, status=status.HTTP_403_FORBIDDEN)
        
        return super().update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        report = self.get_object()
        
        # Only report creator or super admin can delete
        if report.generated_by != request.user and not (hasattr(request.user, 'is_super_admin') and request.user.is_super_admin):
            return Response({
                'error': 'You do not have permission to delete this report'
            }, status=status.HTTP_403_FORBIDDEN)
        
        return super().destroy(request, *args, **kwargs)


class RegenerateReportView(APIView):
    """Regenerate an analytics report"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        try:
            report = AnalyticsReport.objects.get(pk=pk)
        except AnalyticsReport.DoesNotExist:
            return Response({
                'error': 'Report not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check permissions
        user = request.user
        can_regenerate = (
            report.generated_by == user or
            (hasattr(user, 'is_super_admin') and user.is_super_admin) or
            (hasattr(user, 'is_college_admin') and user.is_college_admin)
        )
        
        if not can_regenerate:
            return Response({
                'error': 'You do not have permission to regenerate this report'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Regenerate report
        report.generate_report()
        
        serializer = AnalyticsReportSerializer(report)
        return Response({
            'message': 'Report regeneration completed',
            'report': serializer.data
        }, status=status.HTTP_200_OK)


class DashboardWidgetListView(generics.ListCreateAPIView):
    """Dashboard widgets management"""
    
    serializer_class = DashboardWidgetSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = DashboardWidget.objects.filter(user=user).select_related('club')
        
        # Filter by visibility
        is_visible = self.request.query_params.get('visible')
        if is_visible is not None:
            queryset = queryset.filter(is_visible=is_visible.lower() == 'true')
        
        return queryset.order_by('grid_position')
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class DashboardWidgetDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Dashboard widget detail view"""
    
    serializer_class = DashboardWidgetSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return DashboardWidget.objects.filter(user=self.request.user)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_overview(request):
    """Get dashboard overview with quick stats"""
    user = request.user
    
    # Base queries with user permissions
    if hasattr(user, 'is_super_admin') and user.is_super_admin:
        clubs_query = Club.objects.filter(is_active=True)
        events_query = Event.objects.filter(is_active=True)
        users_query = User.objects.filter(is_active=True)
    elif hasattr(user, 'is_college_admin') and user.is_college_admin:
        clubs_query = Club.objects.filter(is_active=True, college__domain=user.college_email_domain)
        events_query = Event.objects.filter(is_active=True, club__college__domain=user.college_email_domain)
        users_query = User.objects.filter(is_active=True, college_email_domain=user.college_email_domain)
    else:
        # Regular users see public data and their club data
        user_clubs = user.joined_clubs.filter(memberships__status='active')
        clubs_query = user_clubs
        events_query = Event.objects.filter(is_active=True, club__in=user_clubs)
        users_query = User.objects.filter(is_active=True, college_email_domain=user.college_email_domain)
    
    # Calculate quick stats
    total_clubs = clubs_query.count()
    total_events = events_query.count()
    total_users = users_query.count()
    
    # Event stats
    now = timezone.now()
    active_events = events_query.filter(
        start_datetime__lte=now,
        end_datetime__gte=now
    ).count()
    
    upcoming_events = events_query.filter(
        start_datetime__gt=now
    ).count()
    
    # Registration stats
    total_registrations = sum(event.total_registrations for event in events_query)
    
    # Financial stats
    total_revenue = sum(float(event.total_revenue) for event in events_query)
    
    # Attendance rate
    completed_events = events_query.filter(status='completed')
    if completed_events.exists():
        avg_attendance_rate = sum(event.attendance_rate for event in completed_events) / completed_events.count()
    else:
        avg_attendance_rate = 0
    
    stats = QuickStatsSerializer({
        'total_clubs': total_clubs,
        'total_events': total_events,
        'total_users': total_users,
        'total_registrations': total_registrations,
        'active_events': active_events,
        'upcoming_events': upcoming_events,
        'total_revenue': total_revenue,
        'avg_attendance_rate': round(avg_attendance_rate, 2)
    })
    
    return Response({
        'stats': stats.data,
        'timestamp': timezone.now().isoformat()
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def club_analytics(request, club_slug):
    """Get analytics for a specific club"""
    try:
        club = Club.objects.get(slug=club_slug, is_active=True)
    except Club.DoesNotExist:
        return Response({
            'error': 'Club not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check permissions
    user = request.user
    can_view = (
        (hasattr(user, 'is_super_admin') and user.is_super_admin) or
        (hasattr(user, 'is_college_admin') and user.is_college_admin) or
        club.memberships.filter(user=user, status='active').exists()
    )
    
    if not can_view:
        return Response({
            'error': 'You do not have permission to view this club\'s analytics'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get date range from query params
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    
    # Default to last 30 days if no range provided
    if not date_from or not date_to:
        date_to = timezone.now().date()
        date_from = date_to - timedelta(days=30)
    else:
        date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
    
    # Generate analytics data
    events_query = club.events.filter(
        is_active=True,
        start_datetime__date__gte=date_from,
        start_datetime__date__lte=date_to
    )
    
    analytics_data = {
        'club_info': {
            'id': str(club.id),
            'name': club.name,
            'member_count': club.member_count,
            'activity_score': club.activity_score,
        },
        'period': {
            'from': date_from.strftime('%Y-%m-%d'),
            'to': date_to.strftime('%Y-%m-%d'),
        },
        'events': {
            'total': events_query.count(),
            'completed': events_query.filter(status='completed').count(),
            'total_registrations': sum(event.total_registrations for event in events_query),
            'total_attendees': sum(event.total_attendees for event in events_query),
            'total_revenue': sum(float(event.total_revenue) for event in events_query),
        },
        'member_growth': _get_member_growth_data(club, date_from, date_to),
        'event_trends': _get_event_trends_data(events_query),
        'category_distribution': _get_category_distribution(events_query),
        'top_events': [
            {
                'title': event.title,
                'date': event.start_datetime.date().strftime('%Y-%m-%d'),
                'registrations': event.total_registrations,
                'attendees': event.total_attendees,
                'attendance_rate': event.attendance_rate
            }
            for event in sorted(events_query, key=lambda x: x.attendance_rate, reverse=True)[:5]
        ]
    }
    
    return Response(analytics_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def event_analytics(request, event_slug):
    """Get analytics for a specific event"""
    try:
        event = Event.objects.get(slug=event_slug, is_active=True)
    except Event.DoesNotExist:
        return Response({
            'error': 'Event not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check permissions
    user = request.user
    can_view = (
        (hasattr(user, 'is_super_admin') and user.is_super_admin) or
        (hasattr(user, 'is_college_admin') and user.is_college_admin) or
        event.created_by == user or
        event.club.memberships.filter(user=user, status='active', role__in=['admin', 'leader']).exists()
    )
    
    if not can_view:
        return Response({
            'error': 'You do not have permission to view this event\'s analytics'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get registration trends
    registrations = event.registrations.order_by('created_at')
    registration_trends = []
    
    if registrations.exists():
        # Group by day
        current_date = registrations.first().created_at.date()
        end_date = registrations.last().created_at.date()
        
        while current_date <= end_date:
            count = registrations.filter(created_at__date=current_date).count()
            if count > 0:
                registration_trends.append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'registrations': count
                })
            current_date += timedelta(days=1)
    
    # Get demographic breakdown
    demographics = {
        'by_user_type': {},
        'by_college': {},
    }
    
    for registration in registrations.select_related('user'):
        user_type = registration.user.get_user_type_display()
        demographics['by_user_type'][user_type] = demographics['by_user_type'].get(user_type, 0) + 1
        
        college = registration.user.college_name
        demographics['by_college'][college] = demographics['by_college'].get(college, 0) + 1
    
    analytics_data = {
        'event_info': {
            'id': str(event.id),
            'title': event.title,
            'club': event.club.name,
            'date': event.start_datetime.date().strftime('%Y-%m-%d'),
            'status': event.status,
        },
        'registration_stats': {
            'total_registrations': event.total_registrations,
            'total_attendees': event.total_attendees,
            'attendance_rate': event.attendance_rate,
            'revenue': float(event.total_revenue),
        },
        'registration_trends': registration_trends,
        'demographics': demographics,
        'feedback_summary': _get_event_feedback_summary(event),
        'check_in_summary': _get_checkin_summary(event),
    }
    
    return Response(analytics_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chart_data(request):
    """Get chart data for various visualizations"""
    chart_type = request.query_params.get('type')
    period = request.query_params.get('period', '30d')
    
    if not chart_type:
        return Response({
            'error': 'Chart type is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Determine date range
    if period == '7d':
        start_date = timezone.now() - timedelta(days=7)
    elif period == '30d':
        start_date = timezone.now() - timedelta(days=30)
    elif period == '90d':
        start_date = timezone.now() - timedelta(days=90)
    elif period == '1y':
        start_date = timezone.now() - timedelta(days=365)
    else:
        start_date = timezone.now() - timedelta(days=30)
    
    try:
        if chart_type == 'event_registrations_trend':
            chart_data = _get_event_registrations_trend_chart(request.user, start_date)
        elif chart_type == 'club_members_distribution':
            chart_data = _get_club_members_distribution_chart(request.user)
        elif chart_type == 'event_categories_pie':
            chart_data = _get_event_categories_pie_chart(request.user, start_date)
        elif chart_type == 'attendance_rate_comparison':
            chart_data = _get_attendance_rate_comparison_chart(request.user, start_date)
        elif chart_type == 'revenue_trend':
            chart_data = _get_revenue_trend_chart(request.user, start_date)
        else:
            return Response({
                'error': 'Invalid chart type'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = ChartDataSerializer(chart_data)
        return Response(serializer.data)
        
    except Exception as e:
        return Response({
            'error': f'Failed to generate chart data: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def export_analytics(request):
    """Export analytics data"""
    serializer = AnalyticsExportSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    export_type = serializer.validated_data['export_type']
    data_type = serializer.validated_data['data_type']
    date_from = serializer.validated_data.get('date_from')
    date_to = serializer.validated_data.get('date_to')
    filters = serializer.validated_data.get('filters', {})
    
    # Generate export data based on type
    try:
        if data_type == 'club_performance':
            export_data = _generate_club_performance_export(request.user, date_from, date_to, filters)
        elif data_type == 'event_analytics':
            export_data = _generate_event_analytics_export(request.user, date_from, date_to, filters)
        elif data_type == 'user_engagement':
            export_data = _generate_user_engagement_export(request.user, date_from, date_to, filters)
        elif data_type == 'financial_summary':
            export_data = _generate_financial_export(request.user, date_from, date_to, filters)
        else:
            return Response({
                'error': 'Invalid data type'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create export response based on format
        if export_type == 'csv':
            return _create_csv_response(export_data, data_type)
        elif export_type == 'json':
            return Response(export_data)
        elif export_type == 'excel':
            return _create_excel_response(export_data, data_type)
        elif export_type == 'pdf':
            return _create_pdf_response(export_data, data_type)
        
    except Exception as e:
        return Response({
            'error': f'Export failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Helper functions for data generation
def _get_member_growth_data(club, date_from, date_to):
    """Get member growth data for a club over a period"""
    from apps.clubs.models import ClubMembership
    
    growth_data = []
    current_date = date_from
    
    while current_date <= date_to:
        member_count = ClubMembership.objects.filter(
            club=club,
            status='active',
            joined_at__date__lte=current_date
        ).count()
        
        growth_data.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'members': member_count
        })
        
        current_date += timedelta(days=7)  # Weekly intervals
    
    return growth_data


def _get_event_trends_data(events_query):
    """Get event trends data"""
    trends = []
    
    for event in events_query.order_by('start_datetime'):
        trends.append({
            'date': event.start_datetime.date().strftime('%Y-%m-%d'),
            'registrations': event.total_registrations,
            'attendees': event.total_attendees,
            'attendance_rate': event.attendance_rate
        })
    
    return trends


def _get_category_distribution(events_query):
    """Get event category distribution"""
    distribution = {}
    
    for event in events_query.filter(category__isnull=False):
        category = event.category.name
        distribution[category] = distribution.get(category, 0) + 1
    
    return distribution


def _get_event_feedback_summary(event):
    """Get event feedback summary"""
    feedback_entries = event.feedback_entries.filter(is_approved=True)
    
    if not feedback_entries.exists():
        return {
            'total_feedback': 0,
            'average_rating': 0,
            'rating_distribution': {}
        }
    
    ratings = [f.overall_rating for f in feedback_entries]
    avg_rating = sum(ratings) / len(ratings)
    
    rating_distribution = {}
    for rating in ratings:
        rating_distribution[str(rating)] = rating_distribution.get(str(rating), 0) + 1
    
    return {
        'total_feedback': feedback_entries.count(),
        'average_rating': round(avg_rating, 1),
        'rating_distribution': rating_distribution
    }


def _get_checkin_summary(event):
    """Get check-in summary for event"""
    registrations = event.registrations.all()
    
    check_in_methods = {}
    for registration in registrations.filter(status='attended'):
        method = registration.check_in_method
        check_in_methods[method] = check_in_methods.get(method, 0) + 1
    
    return {
        'total_checked_in': event.total_attendees,
        'check_in_methods': check_in_methods,
        'on_time_arrivals': registrations.filter(
            status='attended',
            checked_in_at__lte=event.start_datetime
        ).count()
    }


# Chart data generation functions
def _get_event_registrations_trend_chart(user, start_date):
    """Generate event registrations trend chart data"""
    from apps.events.models import EventRegistration
    
    # Get registrations based on user permissions
    registrations_query = EventRegistration.objects.filter(created_at__gte=start_date)
    
    if hasattr(user, 'is_super_admin') and user.is_super_admin:
        pass  # Can see all
    elif hasattr(user, 'is_college_admin') and user.is_college_admin:
        registrations_query = registrations_query.filter(
            event__club__college__domain=user.college_email_domain
        )
    else:
        user_clubs = user.joined_clubs.filter(memberships__status='active')
        registrations_query = registrations_query.filter(event__club__in=user_clubs)
    
    # Group by day
    daily_counts = {}
    for registration in registrations_query.order_by('created_at'):
        date_key = registration.created_at.date().strftime('%Y-%m-%d')
        daily_counts[date_key] = daily_counts.get(date_key, 0) + 1
    
    # Fill in missing dates with 0
    current_date = start_date.date()
    end_date = timezone.now().date()
    labels = []
    data = []
    
    while current_date <= end_date:
        date_key = current_date.strftime('%Y-%m-%d')
        labels.append(date_key)
        data.append(daily_counts.get(date_key, 0))
        current_date += timedelta(days=1)
    
    return {
        'chart_type': 'line',
        'title': 'Event Registrations Trend',
        'labels': labels,
        'datasets': [{
            'label': 'Registrations',
            'data': data,
            'borderColor': 'rgb(75, 192, 192)',
            'backgroundColor': 'rgba(75, 192, 192, 0.2)',
            'tension': 0.1
        }]
    }


def _get_club_members_distribution_chart(user):
    """Generate club members distribution chart"""
    # Get clubs based on user permissions
    if hasattr(user, 'is_super_admin') and user.is_super_admin:
        clubs = Club.objects.filter(is_active=True)
    elif hasattr(user, 'is_college_admin') and user.is_college_admin:
        clubs = Club.objects.filter(is_active=True, college__domain=user.college_email_domain)
    else:
        clubs = user.joined_clubs.filter(memberships__status='active')
    
    labels = []
    data = []
    colors = [
        'rgb(255, 99, 132)', 'rgb(54, 162, 235)', 'rgb(255, 205, 86)',
        'rgb(75, 192, 192)', 'rgb(153, 102, 255)', 'rgb(255, 159, 64)'
    ]
    
    for i, club in enumerate(clubs[:10]):  # Top 10 clubs
        labels.append(club.name)
        data.append(club.member_count)
    
    return {
        'chart_type': 'bar',
        'title': 'Club Members Distribution',
        'labels': labels,
        'datasets': [{
            'label': 'Members',
            'data': data,
            'backgroundColor': colors[:len(data)],
            'borderWidth': 1
        }]
    }


def _get_event_categories_pie_chart(user, start_date):
    """Generate event categories pie chart"""
    # Get events based on user permissions
    events_query = Event.objects.filter(is_active=True, start_datetime__gte=start_date)
    
    if hasattr(user, 'is_super_admin') and user.is_super_admin:
        pass
    elif hasattr(user, 'is_college_admin') and user.is_college_admin:
        events_query = events_query.filter(club__college__domain=user.college_email_domain)
    else:
        user_clubs = user.joined_clubs.filter(memberships__status='active')
        events_query = events_query.filter(club__in=user_clubs)
    
    # Count by category
    category_counts = {}
    for event in events_query.filter(category__isnull=False):
        category = event.category.name
        category_counts[category] = category_counts.get(category, 0) + 1
    
    labels = list(category_counts.keys())
    data = list(category_counts.values())
    colors = [
        'rgb(255, 99, 132)', 'rgb(54, 162, 235)', 'rgb(255, 205, 86)',
        'rgb(75, 192, 192)', 'rgb(153, 102, 255)', 'rgb(255, 159, 64)'
    ]
    
    return {
        'chart_type': 'pie',
        'title': 'Events by Category',
        'labels': labels,
        'datasets': [{
            'data': data,
            'backgroundColor': colors[:len(data)],
            'borderWidth': 1
        }]
    }


def _get_attendance_rate_comparison_chart(user, start_date):
    """Generate attendance rate comparison chart"""
    # Implementation for attendance rate comparison
    return {
        'chart_type': 'bar',
        'title': 'Attendance Rate Comparison',
        'labels': [],
        'datasets': []
    }


def _get_revenue_trend_chart(user, start_date):
    """Generate revenue trend chart"""
    # Implementation for revenue trends
    return {
        'chart_type': 'line',
        'title': 'Revenue Trend',
        'labels': [],
        'datasets': []
    }


# Export helper functions
def _generate_club_performance_export(user, date_from, date_to, filters):
    """Generate club performance export data"""
    return {'clubs': []}


def _generate_event_analytics_export(user, date_from, date_to, filters):
    """Generate event analytics export data"""
    return {'events': []}


def _generate_user_engagement_export(user, date_from, date_to, filters):
    """Generate user engagement export data"""
    return {'users': []}


def _generate_financial_export(user, date_from, date_to, filters):
    """Generate financial export data"""
    return {'financial_data': []}


def _create_csv_response(data, data_type):
    """Create CSV response"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{data_type}_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Export Data'])  # Simplified for now
    
    return response


def _create_excel_response(data, data_type):
    """Create Excel response"""
    # Implementation for Excel export
    pass


def _create_pdf_response(data, data_type):
    """Create PDF response"""
    # Implementation for PDF export
    pass
