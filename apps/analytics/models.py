"""
Analytics models for Campus Club Management Suite
Comprehensive analytics tracking and reporting system
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Avg, Sum
from decimal import Decimal
import uuid
import json

class AnalyticsReport(models.Model):
    """Base model for storing generated analytics reports"""
    
    REPORT_TYPES = [
        ('club_performance', 'Club Performance'),
        ('event_analytics', 'Event Analytics'),
        ('user_engagement', 'User Engagement'),
        ('financial_summary', 'Financial Summary'),
        ('collaboration_metrics', 'Collaboration Metrics'),
        ('college_overview', 'College Overview'),
        ('monthly_summary', 'Monthly Summary'),
        ('custom', 'Custom Report'),
    ]
    
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
        ('one_time', 'One Time'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    report_type = models.CharField(max_length=30, choices=REPORT_TYPES)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='one_time')
    
    # Scope and Filters
    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, null=True, blank=True, related_name='analytics_reports')
    college = models.ForeignKey('authentication.College', on_delete=models.CASCADE, null=True, blank=True, related_name='analytics_reports')
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    
    # Report Data
    data = models.JSONField(default=dict, blank=True)
    summary = models.JSONField(default=dict, blank=True)
    charts_config = models.JSONField(default=dict, blank=True)
    
    # Metadata
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='generated_reports')
    is_scheduled = models.BooleanField(default=False)
    is_public = models.BooleanField(default=False)
    
    # Status
    status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', 'Pending'),
        ('generating', 'Generating'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ])
    error_message = models.TextField(blank=True)
    
    # Timing
    generation_started_at = models.DateTimeField(null=True, blank=True)
    generation_completed_at = models.DateTimeField(null=True, blank=True)
    next_generation_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'analytics_reports'
        verbose_name = 'Analytics Report'
        verbose_name_plural = 'Analytics Reports'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['report_type', 'status']),
            models.Index(fields=['club', 'date_from', 'date_to']),
            models.Index(fields=['is_scheduled', 'next_generation_at']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_report_type_display()})"
    
    def generate_report(self):
        """Generate the analytics report based on type"""
        self.status = 'generating'
        self.generation_started_at = timezone.now()
        self.save()
        
        try:
            if self.report_type == 'club_performance':
                self.data = self._generate_club_performance()
            elif self.report_type == 'event_analytics':
                self.data = self._generate_event_analytics()
            elif self.report_type == 'user_engagement':
                self.data = self._generate_user_engagement()
            elif self.report_type == 'financial_summary':
                self.data = self._generate_financial_summary()
            elif self.report_type == 'collaboration_metrics':
                self.data = self._generate_collaboration_metrics()
            elif self.report_type == 'college_overview':
                self.data = self._generate_college_overview()
            elif self.report_type == 'monthly_summary':
                self.data = self._generate_monthly_summary()
            
            self.status = 'completed'
            self.generation_completed_at = timezone.now()
            self._generate_summary()
            
        except Exception as e:
            self.status = 'failed'
            self.error_message = str(e)
        
        self.save()
    
    def _generate_club_performance(self):
        """Generate club performance analytics"""
        from apps.clubs.models import Club, ClubMembership
        from apps.events.models import Event
        
        # Get club or all clubs
        if self.club:
            clubs = [self.club]
        else:
            clubs = Club.objects.filter(is_active=True)
            if self.college:
                clubs = clubs.filter(college=self.college)
        
        data = {
            'clubs': [],
            'totals': {
                'total_clubs': len(clubs),
                'total_members': 0,
                'total_events': 0,
                'avg_activity_score': 0,
            },
            'trends': [],
        }
        
        for club in clubs:
            # Date filtering for events
            events_query = club.events.filter(is_active=True)
            if self.date_from:
                events_query = events_query.filter(start_datetime__date__gte=self.date_from)
            if self.date_to:
                events_query = events_query.filter(start_datetime__date__lte=self.date_to)
            
            # Member growth over time
            member_growth = []
            if self.date_from and self.date_to:
                from dateutil.relativedelta import relativedelta
                current_date = self.date_from
                while current_date <= self.date_to:
                    member_count = club.memberships.filter(
                        status='active',
                        joined_at__date__lte=current_date
                    ).count()
                    member_growth.append({
                        'date': current_date.strftime('%Y-%m-%d'),
                        'count': member_count
                    })
                    current_date += relativedelta(months=1)
            
            club_data = {
                'id': str(club.id),
                'name': club.name,
                'member_count': club.member_count,
                'event_count': events_query.count(),
                'activity_score': club.activity_score,
                'avg_event_attendance': self._calculate_avg_attendance(events_query),
                'member_growth': member_growth,
                'event_categories': self._get_event_categories_distribution(events_query),
                'recent_events': [
                    {
                        'title': event.title,
                        'date': event.start_datetime.date().strftime('%Y-%m-%d'),
                        'attendance': event.total_attendees,
                        'capacity': event.max_attendees
                    }
                    for event in events_query.order_by('-start_datetime')[:5]
                ]
            }
            
            data['clubs'].append(club_data)
            data['totals']['total_members'] += club_data['member_count']
            data['totals']['total_events'] += club_data['event_count']
        
        if data['clubs']:
            data['totals']['avg_activity_score'] = sum(c['activity_score'] for c in data['clubs']) / len(data['clubs'])
        
        return data
    
    def _generate_event_analytics(self):
        """Generate event analytics"""
        from apps.events.models import Event, EventRegistration
        
        # Get events based on filters
        events_query = Event.objects.filter(is_active=True)
        
        if self.club:
            events_query = events_query.filter(club=self.club)
        if self.college:
            events_query = events_query.filter(club__college=self.college)
        if self.date_from:
            events_query = events_query.filter(start_datetime__date__gte=self.date_from)
        if self.date_to:
            events_query = events_query.filter(start_datetime__date__lte=self.date_to)
        
        events = events_query.select_related('club', 'category')
        
        data = {
            'summary': {
                'total_events': events.count(),
                'total_registrations': sum(e.total_registrations for e in events),
                'total_attendees': sum(e.total_attendees for e in events),
                'avg_attendance_rate': 0,
                'total_revenue': sum(e.total_revenue for e in events),
            },
            'by_type': {},
            'by_category': {},
            'by_month': {},
            'top_events': [],
            'attendance_trends': [],
        }
        
        if data['summary']['total_registrations'] > 0:
            data['summary']['avg_attendance_rate'] = round(
                (data['summary']['total_attendees'] / data['summary']['total_registrations']) * 100, 2
            )
        
        # Group by event type
        type_stats = {}
        for event in events:
            event_type = event.get_event_type_display()
            if event_type not in type_stats:
                type_stats[event_type] = {
                    'count': 0,
                    'registrations': 0,
                    'attendees': 0,
                    'revenue': Decimal('0.00')
                }
            
            type_stats[event_type]['count'] += 1
            type_stats[event_type]['registrations'] += event.total_registrations
            type_stats[event_type]['attendees'] += event.total_attendees
            type_stats[event_type]['revenue'] += event.total_revenue
        
        data['by_type'] = type_stats
        
        # Group by category
        category_stats = {}
        for event in events.filter(category__isnull=False):
            category_name = event.category.name
            if category_name not in category_stats:
                category_stats[category_name] = {
                    'count': 0,
                    'registrations': 0,
                    'attendees': 0
                }
            
            category_stats[category_name]['count'] += 1
            category_stats[category_name]['registrations'] += event.total_registrations
            category_stats[category_name]['attendees'] += event.total_attendees
        
        data['by_category'] = category_stats
        
        # Top performing events
        data['top_events'] = [
            {
                'title': event.title,
                'club': event.club.name,
                'date': event.start_datetime.date().strftime('%Y-%m-%d'),
                'registrations': event.total_registrations,
                'attendees': event.total_attendees,
                'attendance_rate': event.attendance_rate,
                'revenue': float(event.total_revenue)
            }
            for event in sorted(events, key=lambda x: x.attendance_rate, reverse=True)[:10]
        ]
        
        return data
    
    def _generate_user_engagement(self):
        """Generate user engagement analytics"""
        from apps.authentication.models import User
        from apps.clubs.models import ClubMembership
        from apps.events.models import EventRegistration
        
        # Get users based on filters
        users_query = User.objects.filter(is_active=True)
        if self.college:
            users_query = users_query.filter(college_email_domain=self.college.domain)
        
        data = {
            'user_stats': {
                'total_users': users_query.count(),
                'active_users': 0,
                'club_members': 0,
                'event_participants': 0,
            },
            'engagement_levels': {
                'high': 0,
                'medium': 0,
                'low': 0,
                'inactive': 0,
            },
            'user_types': {},
            'activity_trends': [],
            'top_users': []
        }
        
        # Calculate engagement metrics
        for user in users_query.select_related('profile'):
            # Activity score calculation
            club_count = user.joined_clubs.filter(memberships__status='active').count()
            event_count = user.event_registrations.filter(status='attended').count()
            
            activity_score = club_count * 10 + event_count * 5
            
            # Categorize engagement
            if activity_score >= 50:
                data['engagement_levels']['high'] += 1
            elif activity_score >= 20:
                data['engagement_levels']['medium'] += 1
            elif activity_score >= 5:
                data['engagement_levels']['low'] += 1
            else:
                data['engagement_levels']['inactive'] += 1
            
            # User type distribution
            user_type = user.get_user_type_display()
            if user_type not in data['user_types']:
                data['user_types'][user_type] = 0
            data['user_types'][user_type] += 1
            
            # Activity tracking
            if club_count > 0:
                data['user_stats']['club_members'] += 1
            if event_count > 0:
                data['user_stats']['event_participants'] += 1
            
            # Last activity check
            if hasattr(user, 'last_activity') and user.last_activity:
                days_since_activity = (timezone.now() - user.last_activity).days
                if days_since_activity <= 7:
                    data['user_stats']['active_users'] += 1
        
        return data
    
    def _generate_financial_summary(self):
        """Generate financial analytics"""
        from apps.events.models import Event
        from apps.clubs.models import Club
        
        data = {
            'revenue': {
                'total_event_revenue': Decimal('0.00'),
                'total_membership_fees': Decimal('0.00'),
                'by_club': {},
                'by_month': {},
            },
            'expenses': {
                'total_budgets': Decimal('0.00'),
                'budget_utilization': {},
            },
            'projections': {},
        }
        
        # Event revenue
        events_query = Event.objects.filter(is_active=True)
        if self.club:
            events_query = events_query.filter(club=self.club)
        if self.college:
            events_query = events_query.filter(club__college=self.college)
        if self.date_from:
            events_query = events_query.filter(start_datetime__date__gte=self.date_from)
        if self.date_to:
            events_query = events_query.filter(start_datetime__date__lte=self.date_to)
        
        for event in events_query:
            data['revenue']['total_event_revenue'] += event.total_revenue
            
            club_name = event.club.name
            if club_name not in data['revenue']['by_club']:
                data['revenue']['by_club'][club_name] = Decimal('0.00')
            data['revenue']['by_club'][club_name] += event.total_revenue
        
        # Club budgets
        clubs_query = Club.objects.filter(is_active=True)
        if self.college:
            clubs_query = clubs_query.filter(college=self.college)
        
        for club in clubs_query:
            data['expenses']['total_budgets'] += club.budget
            
            # Calculate budget utilization (simplified)
            utilized = sum(event.total_revenue for event in club.events.filter(is_active=True))
            if club.budget > 0:
                utilization_rate = float((utilized / club.budget) * 100)
                data['expenses']['budget_utilization'][club.name] = {
                    'budget': float(club.budget),
                    'utilized': float(utilized),
                    'utilization_rate': utilization_rate
                }
        
        # Convert Decimal to float for JSON serialization
        data['revenue']['total_event_revenue'] = float(data['revenue']['total_event_revenue'])
        data['revenue']['total_membership_fees'] = float(data['revenue']['total_membership_fees'])
        data['expenses']['total_budgets'] = float(data['expenses']['total_budgets'])
        
        for club_name in data['revenue']['by_club']:
            data['revenue']['by_club'][club_name] = float(data['revenue']['by_club'][club_name])
        
        return data
    
    def _generate_collaboration_metrics(self):
        """Generate collaboration analytics"""
        # This would connect to collaboration app when implemented
        return {
            'total_collaborations': 0,
            'active_partnerships': 0,
            'cross_college_projects': 0,
            'success_rate': 0,
            'by_category': {},
            'trends': []
        }
    
    def _generate_college_overview(self):
        """Generate college-wide overview"""
        if not self.college:
            return {}
        
        from apps.clubs.models import Club
        from apps.events.models import Event
        from apps.authentication.models import User
        
        clubs = Club.objects.filter(college=self.college, is_active=True)
        events = Event.objects.filter(club__college=self.college, is_active=True)
        users = User.objects.filter(college_email_domain=self.college.domain, is_active=True)
        
        if self.date_from:
            events = events.filter(start_datetime__date__gte=self.date_from)
        if self.date_to:
            events = events.filter(start_datetime__date__lte=self.date_to)
        
        data = {
            'college_info': {
                'name': self.college.name,
                'total_clubs': clubs.count(),
                'total_events': events.count(),
                'total_users': users.count(),
                'total_registrations': sum(e.total_registrations for e in events),
            },
            'club_categories': {},
            'event_types': {},
            'user_engagement': {},
            'growth_trends': []
        }
        
        return data
    
    def _generate_monthly_summary(self):
        """Generate monthly summary report"""
        from datetime import datetime
        from dateutil.relativedelta import relativedelta
        
        # Default to current month if no dates provided
        if not self.date_from or not self.date_to:
            now = timezone.now()
            self.date_from = now.replace(day=1).date()
            self.date_to = (now.replace(day=1) + relativedelta(months=1) - timezone.timedelta(days=1)).date()
        
        data = {
            'period': {
                'from': self.date_from.strftime('%Y-%m-%d'),
                'to': self.date_to.strftime('%Y-%m-%d'),
                'month_name': self.date_from.strftime('%B %Y')
            },
            'highlights': {},
            'comparisons': {},
            'achievements': []
        }
        
        return data
    
    def _generate_summary(self):
        """Generate report summary from data"""
        if not self.data:
            return
        
        summary = {
            'generated_at': timezone.now().isoformat(),
            'period': f"{self.date_from} to {self.date_to}" if self.date_from and self.date_to else "All time",
            'key_metrics': [],
        }
        
        if self.report_type == 'club_performance' and 'totals' in self.data:
            summary['key_metrics'] = [
                {'label': 'Total Clubs', 'value': self.data['totals']['total_clubs']},
                {'label': 'Total Members', 'value': self.data['totals']['total_members']},
                {'label': 'Total Events', 'value': self.data['totals']['total_events']},
                {'label': 'Avg Activity Score', 'value': round(self.data['totals']['avg_activity_score'], 2)},
            ]
        
        elif self.report_type == 'event_analytics' and 'summary' in self.data:
            summary['key_metrics'] = [
                {'label': 'Total Events', 'value': self.data['summary']['total_events']},
                {'label': 'Total Registrations', 'value': self.data['summary']['total_registrations']},
                {'label': 'Total Attendees', 'value': self.data['summary']['total_attendees']},
                {'label': 'Avg Attendance Rate', 'value': f"{self.data['summary']['avg_attendance_rate']}%"},
                {'label': 'Total Revenue', 'value': f"${self.data['summary']['total_revenue']}"},
            ]
        
        self.summary = summary
    
    def _calculate_avg_attendance(self, events_query):
        """Calculate average attendance rate for events"""
        total_rate = 0
        event_count = 0
        
        for event in events_query:
            if event.total_registrations > 0:
                total_rate += event.attendance_rate
                event_count += 1
        
        return round(total_rate / event_count, 2) if event_count > 0 else 0
    
    def _get_event_categories_distribution(self, events_query):
        """Get distribution of events by category"""
        distribution = {}
        for event in events_query.filter(category__isnull=False):
            category = event.category.name
            distribution[category] = distribution.get(category, 0) + 1
        return distribution


class DashboardWidget(models.Model):
    """Dashboard widget configuration"""
    
    WIDGET_TYPES = [
        ('metric_card', 'Metric Card'),
        ('line_chart', 'Line Chart'),
        ('bar_chart', 'Bar Chart'),
        ('pie_chart', 'Pie Chart'),
        ('table', 'Data Table'),
        ('progress_bar', 'Progress Bar'),
        ('gauge', 'Gauge Chart'),
        ('heatmap', 'Heat Map'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPES)
    
    # Configuration
    data_source = models.CharField(max_length=100)  # API endpoint or data query
    config = models.JSONField(default=dict, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    
    # Layout
    grid_position = models.JSONField(default=dict, blank=True)  # x, y, width, height
    is_visible = models.BooleanField(default=True)
    
    # Access Control
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='dashboard_widgets')
    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, null=True, blank=True, related_name='dashboard_widgets')
    is_shared = models.BooleanField(default=False)
    
    # Refresh Settings
    auto_refresh = models.BooleanField(default=True)
    refresh_interval = models.IntegerField(default=300)  # seconds
    last_updated = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'dashboard_widgets'
        verbose_name = 'Dashboard Widget'
        verbose_name_plural = 'Dashboard Widgets'
        ordering = ['grid_position']
    
    def __str__(self):
        return f"{self.title} ({self.get_widget_type_display()})"
    
    def refresh_data(self):
        """Refresh widget data"""
        self.last_updated = timezone.now()
        self.save()
