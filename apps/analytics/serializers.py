"""
Analytics serializers for Campus Club Management Suite
Seamless API serialization for analytics and dashboard data
"""
from rest_framework import serializers
from django.utils import timezone
from django.db.models import Count, Avg, Sum
from datetime import datetime, timedelta
from .models import AnalyticsReport, DashboardWidget

class AnalyticsReportSerializer(serializers.ModelSerializer):
    """Serializer for AnalyticsReport model"""
    
    generated_by = serializers.StringRelatedField(read_only=True)
    club_name = serializers.CharField(source='club.name', read_only=True)
    college_name = serializers.CharField(source='college.name', read_only=True)
    generation_duration = serializers.SerializerMethodField()
    is_outdated = serializers.SerializerMethodField()
    
    class Meta:
        model = AnalyticsReport
        fields = [
            'id', 'title', 'report_type', 'frequency', 'club_name', 'college_name',
            'date_from', 'date_to', 'filters', 'data', 'summary', 'charts_config',
            'generated_by', 'is_scheduled', 'is_public', 'status', 'error_message',
            'generation_started_at', 'generation_completed_at', 'next_generation_at',
            'generation_duration', 'is_outdated', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'data', 'summary', 'charts_config', 'generated_by', 'status',
            'error_message', 'generation_started_at', 'generation_completed_at',
            'generation_duration', 'is_outdated', 'created_at', 'updated_at'
        ]
    
    def get_generation_duration(self, obj):
        """Get report generation duration in seconds"""
        if obj.generation_started_at and obj.generation_completed_at:
            duration = obj.generation_completed_at - obj.generation_started_at
            return duration.total_seconds()
        return None
    
    def get_is_outdated(self, obj):
        """Check if report data is outdated"""
        if not obj.generation_completed_at:
            return True
        
        # Consider report outdated after specific periods based on frequency
        outdated_periods = {
            'daily': timedelta(days=1),
            'weekly': timedelta(days=7),
            'monthly': timedelta(days=30),
            'quarterly': timedelta(days=90),
            'yearly': timedelta(days=365),
            'one_time': timedelta(days=30),  # One-time reports expire after 30 days
        }
        
        outdated_after = outdated_periods.get(obj.frequency, timedelta(days=7))
        return timezone.now() - obj.generation_completed_at > outdated_after


class AnalyticsReportCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating analytics reports"""
    
    class Meta:
        model = AnalyticsReport
        fields = [
            'title', 'report_type', 'frequency', 'club', 'college',
            'date_from', 'date_to', 'filters', 'is_scheduled', 'is_public'
        ]
    
    def validate(self, attrs):
        """Validate report parameters"""
        date_from = attrs.get('date_from')
        date_to = attrs.get('date_to')
        
        if date_from and date_to:
            if date_to < date_from:
                raise serializers.ValidationError("End date must be after start date.")
            
            # Check if date range is too large
            if (date_to - date_from).days > 365:
                raise serializers.ValidationError("Date range cannot exceed 365 days.")
        
        report_type = attrs.get('report_type')
        club = attrs.get('club')
        college = attrs.get('college')
        
        # Some report types require specific scope
        if report_type == 'club_performance' and not club and not college:
            raise serializers.ValidationError("Club performance reports require either a club or college scope.")
        
        if report_type == 'college_overview' and not college:
            raise serializers.ValidationError("College overview reports require a college scope.")
        
        return attrs
    
    def create(self, validated_data):
        """Create and optionally generate report"""
        request = self.context.get('request')
        
        report = AnalyticsReport.objects.create(
            generated_by=request.user,
            **validated_data
        )
        
        # Auto-generate if not scheduled
        if not validated_data.get('is_scheduled', False):
            report.generate_report()
        
        return report


class DashboardWidgetSerializer(serializers.ModelSerializer):
    """Serializer for DashboardWidget model"""
    
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    club_name = serializers.CharField(source='club.name', read_only=True)
    data = serializers.SerializerMethodField()
    
    class Meta:
        model = DashboardWidget
        fields = [
            'id', 'title', 'widget_type', 'data_source', 'config', 'filters',
            'grid_position', 'is_visible', 'user_name', 'club_name', 'is_shared',
            'auto_refresh', 'refresh_interval', 'last_updated', 'data',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user_name', 'club_name', 'data', 'last_updated', 'created_at', 'updated_at']
    
    def get_data(self, obj):
        """Get widget data based on data source"""
        try:
            return self._fetch_widget_data(obj)
        except Exception as e:
            return {'error': str(e), 'timestamp': timezone.now().isoformat()}
    
    def _fetch_widget_data(self, widget):
        """Fetch data for specific widget types"""
        data_source = widget.data_source
        filters = widget.filters or {}
        
        if data_source == 'club_members_count':
            return self._get_club_members_data(widget, filters)
        elif data_source == 'event_registrations':
            return self._get_event_registrations_data(widget, filters)
        elif data_source == 'financial_summary':
            return self._get_financial_data(widget, filters)
        elif data_source == 'user_engagement':
            return self._get_user_engagement_data(widget, filters)
        elif data_source == 'event_attendance_trends':
            return self._get_attendance_trends_data(widget, filters)
        else:
            return {'value': 0, 'label': 'No Data'}
    
    def _get_club_members_data(self, widget, filters):
        """Get club members count data"""
        from apps.clubs.models import Club, ClubMembership
        
        if widget.club:
            count = widget.club.member_count
            growth = self._calculate_member_growth(widget.club, filters.get('period', '30d'))
            return {
                'value': count,
                'label': 'Total Members',
                'growth': growth,
                'timestamp': timezone.now().isoformat()
            }
        else:
            # All clubs data for user's college/access
            clubs = Club.objects.filter(is_active=True)
            total_members = sum(club.member_count for club in clubs)
            return {
                'value': total_members,
                'label': 'Total Members (All Clubs)',
                'timestamp': timezone.now().isoformat()
            }
    
    def _get_event_registrations_data(self, widget, filters):
        """Get event registrations data"""
        from apps.events.models import Event, EventRegistration
        
        events_query = Event.objects.filter(is_active=True)
        if widget.club:
            events_query = events_query.filter(club=widget.club)
        
        # Apply time filter
        period = filters.get('period', '30d')
        if period == '7d':
            start_date = timezone.now() - timedelta(days=7)
        elif period == '30d':
            start_date = timezone.now() - timedelta(days=30)
        elif period == '90d':
            start_date = timezone.now() - timedelta(days=90)
        else:
            start_date = timezone.now() - timedelta(days=30)
        
        events = events_query.filter(start_datetime__gte=start_date)
        total_registrations = sum(event.total_registrations for event in events)
        
        return {
            'value': total_registrations,
            'label': f'Registrations ({period})',
            'events_count': events.count(),
            'avg_per_event': round(total_registrations / events.count(), 1) if events.count() > 0 else 0,
            'timestamp': timezone.now().isoformat()
        }
    
    def _get_financial_data(self, widget, filters):
        """Get financial summary data"""
        from apps.events.models import Event
        
        events_query = Event.objects.filter(is_active=True)
        if widget.club:
            events_query = events_query.filter(club=widget.club)
        
        period = filters.get('period', '30d')
        if period == '7d':
            start_date = timezone.now() - timedelta(days=7)
        elif period == '30d':
            start_date = timezone.now() - timedelta(days=30)
        elif period == '90d':
            start_date = timezone.now() - timedelta(days=90)
        else:
            start_date = timezone.now() - timedelta(days=30)
        
        events = events_query.filter(start_datetime__gte=start_date)
        total_revenue = sum(float(event.total_revenue) for event in events)
        
        return {
            'value': total_revenue,
            'label': f'Revenue ({period})',
            'currency': 'USD',
            'events_count': events.count(),
            'timestamp': timezone.now().isoformat()
        }
    
    def _get_user_engagement_data(self, widget, filters):
        """Get user engagement metrics"""
        from apps.authentication.models import User
        from apps.clubs.models import ClubMembership
        
        # Get active users in the last 7 days
        week_ago = timezone.now() - timedelta(days=7)
        active_users = User.objects.filter(
            is_active=True,
            last_activity__gte=week_ago
        ).count()
        
        # Get total users
        total_users = User.objects.filter(is_active=True).count()
        
        engagement_rate = round((active_users / total_users) * 100, 1) if total_users > 0 else 0
        
        return {
            'value': engagement_rate,
            'label': 'Weekly Engagement Rate (%)',
            'active_users': active_users,
            'total_users': total_users,
            'timestamp': timezone.now().isoformat()
        }
    
    def _get_attendance_trends_data(self, widget, filters):
        """Get event attendance trends"""
        from apps.events.models import Event
        
        events_query = Event.objects.filter(is_active=True, status='completed')
        if widget.club:
            events_query = events_query.filter(club=widget.club)
        
        # Get last 30 days of events
        thirty_days_ago = timezone.now() - timedelta(days=30)
        events = events_query.filter(
            start_datetime__gte=thirty_days_ago
        ).order_by('start_datetime')
        
        trends = []
        for event in events:
            trends.append({
                'date': event.start_datetime.date().strftime('%Y-%m-%d'),
                'attendance_rate': event.attendance_rate,
                'attendees': event.total_attendees,
                'registrations': event.total_registrations
            })
        
        avg_attendance_rate = round(
            sum(event.attendance_rate for event in events) / events.count(), 1
        ) if events.count() > 0 else 0
        
        return {
            'trends': trends,
            'avg_attendance_rate': avg_attendance_rate,
            'events_count': events.count(),
            'timestamp': timezone.now().isoformat()
        }
    
    def _calculate_member_growth(self, club, period):
        """Calculate member growth for a period"""
        from apps.clubs.models import ClubMembership
        
        if period == '7d':
            start_date = timezone.now() - timedelta(days=7)
        elif period == '30d':
            start_date = timezone.now() - timedelta(days=30)
        else:
            start_date = timezone.now() - timedelta(days=30)
        
        new_members = ClubMembership.objects.filter(
            club=club,
            status='active',
            joined_at__gte=start_date
        ).count()
        
        return {
            'new_members': new_members,
            'period': period,
            'growth_rate': round((new_members / club.member_count) * 100, 1) if club.member_count > 0 else 0
        }


class QuickStatsSerializer(serializers.Serializer):
    """Serializer for quick dashboard statistics"""
    
    total_clubs = serializers.IntegerField()
    total_events = serializers.IntegerField()
    total_users = serializers.IntegerField()
    total_registrations = serializers.IntegerField()
    active_events = serializers.IntegerField()
    upcoming_events = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    avg_attendance_rate = serializers.FloatField()


class ChartDataSerializer(serializers.Serializer):
    """Serializer for chart data"""
    
    chart_type = serializers.ChoiceField(choices=[
        ('line', 'Line Chart'),
        ('bar', 'Bar Chart'),
        ('pie', 'Pie Chart'),
        ('area', 'Area Chart'),
        ('doughnut', 'Doughnut Chart'),
    ])
    title = serializers.CharField()
    labels = serializers.ListField(child=serializers.CharField())
    datasets = serializers.ListField()
    options = serializers.DictField(default=dict)


class AnalyticsExportSerializer(serializers.Serializer):
    """Serializer for analytics export requests"""
    
    export_type = serializers.ChoiceField(choices=[
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('pdf', 'PDF'),
        ('json', 'JSON'),
    ])
    data_type = serializers.ChoiceField(choices=[
        ('club_performance', 'Club Performance'),
        ('event_analytics', 'Event Analytics'),
        ('user_engagement', 'User Engagement'),
        ('financial_summary', 'Financial Summary'),
    ])
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    filters = serializers.DictField(default=dict, required=False)
    
    def validate(self, attrs):
        """Validate export parameters"""
        date_from = attrs.get('date_from')
        date_to = attrs.get('date_to')
        
        if date_from and date_to:
            if date_to < date_from:
                raise serializers.ValidationError("End date must be after start date.")
            
            # Limit export range
            if (date_to - date_from).days > 365:
                raise serializers.ValidationError("Export range cannot exceed 365 days.")
        
        return attrs
