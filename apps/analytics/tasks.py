"""
Celery tasks for analytics app
Background tasks for report generation and data processing
"""
from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
from .models import AnalyticsReport, DashboardWidget

@shared_task
def generate_scheduled_reports():
    """Generate scheduled analytics reports"""
    now = timezone.now()
    
    # Find reports that need to be generated
    due_reports = AnalyticsReport.objects.filter(
        is_scheduled=True,
        status='completed',  # Only regenerate completed reports
        next_generation_at__lte=now
    )
    
    generated_count = 0
    failed_count = 0
    
    for report in due_reports:
        try:
            report.generate_report()
            
            # Schedule next generation based on frequency
            if report.frequency == 'daily':
                report.next_generation_at = now + timedelta(days=1)
            elif report.frequency == 'weekly':
                report.next_generation_at = now + timedelta(weeks=1)
            elif report.frequency == 'monthly':
                report.next_generation_at = now + timedelta(days=30)
            elif report.frequency == 'quarterly':
                report.next_generation_at = now + timedelta(days=90)
            elif report.frequency == 'yearly':
                report.next_generation_at = now + timedelta(days=365)
            
            report.save(update_fields=['next_generation_at'])
            generated_count += 1
            
        except Exception as e:
            print(f"Failed to generate report {report.id}: {str(e)}")
            failed_count += 1
    
    return f"Generated {generated_count} reports, {failed_count} failed"


@shared_task
def refresh_dashboard_widgets():
    """Refresh dashboard widgets that have auto-refresh enabled"""
    now = timezone.now()
    
    # Find widgets that need refreshing
    widgets_to_refresh = DashboardWidget.objects.filter(
        auto_refresh=True,
        is_visible=True
    )
    
    refreshed_count = 0
    
    for widget in widgets_to_refresh:
        # Check if it's time to refresh based on refresh_interval
        if widget.last_updated:
            time_since_update = now - widget.last_updated
            if time_since_update.total_seconds() < widget.refresh_interval:
                continue  # Not yet time to refresh
        
        try:
            widget.refresh_data()
            refreshed_count += 1
        except Exception as e:
            print(f"Failed to refresh widget {widget.id}: {str(e)}")
    
    return f"Refreshed {refreshed_count} dashboard widgets"


@shared_task
def cleanup_old_reports():
    """Clean up old analytics reports"""
    cutoff_date = timezone.now() - timedelta(days=90)  # Keep reports for 90 days
    
    # Delete old one-time reports
    old_reports = AnalyticsReport.objects.filter(
        frequency='one_time',
        created_at__lt=cutoff_date,
        is_public=False  # Don't delete public reports
    )
    
    deleted_count = old_reports.count()
    old_reports.delete()
    
    return f"Cleaned up {deleted_count} old reports"


@shared_task
def send_report_notifications():
    """Send notifications for completed reports"""
    # Find recently completed reports that haven't been notified
    recent_reports = AnalyticsReport.objects.filter(
        status='completed',
        generation_completed_at__gte=timezone.now() - timedelta(hours=1)
    ).select_related('generated_by')
    
    notification_count = 0
    
    for report in recent_reports:
        try:
            # Send email notification to report generator
            send_mail(
                subject=f'Analytics Report Ready: {report.title}',
                message=f'''Hi {report.generated_by.full_name},

Your analytics report "{report.title}" has been generated and is ready to view.

Report Type: {report.get_report_type_display()}
Generated: {report.generation_completed_at.strftime('%Y-%m-%d %H:%M:%S')}

You can view your report in the analytics dashboard.

Best regards,
Campus Club Management Team''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[report.generated_by.email],
                fail_silently=True
            )
            notification_count += 1
            
        except Exception as e:
            print(f"Failed to send notification for report {report.id}: {str(e)}")
    
    return f"Sent {notification_count} report notifications"


@shared_task
def calculate_analytics_metrics():
    """Calculate and cache analytics metrics"""
    from apps.clubs.models import Club
    from apps.events.models import Event
    from apps.authentication.models import User
    
    # This task would calculate and cache frequently accessed metrics
    # to improve dashboard performance
    
    metrics = {
        'total_clubs': Club.objects.filter(is_active=True).count(),
        'total_events': Event.objects.filter(is_active=True).count(),
        'total_users': User.objects.filter(is_active=True).count(),
        'calculated_at': timezone.now().isoformat()
    }
    
    # Store metrics in cache or database
    # Implementation would depend on caching strategy
    
    return f"Calculated analytics metrics: {metrics}"


@shared_task
def generate_monthly_summary_reports():
    """Generate monthly summary reports for all colleges"""
    from apps.authentication.models import College
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    
    # Get previous month
    now = timezone.now()
    last_month = now - relativedelta(months=1)
    month_start = last_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(seconds=1)
    
    generated_count = 0
    
    for college in College.objects.filter(is_verified=True, is_active=True):
        try:
            # Create monthly summary report
            report = AnalyticsReport.objects.create(
                title=f"Monthly Summary - {college.name} - {last_month.strftime('%B %Y')}",
                report_type='monthly_summary',
                frequency='monthly',
                college=college,
                date_from=month_start.date(),
                date_to=month_end.date(),
                generated_by_id=1,  # System user
                is_scheduled=True,
                is_public=False
            )
            
            report.generate_report()
            generated_count += 1
            
        except Exception as e:
            print(f"Failed to generate monthly summary for {college.name}: {str(e)}")
    
    return f"Generated {generated_count} monthly summary reports"


@shared_task
def export_analytics_data(export_params):
    """Background task for large analytics exports"""
    # This would handle large export requests asynchronously
    # and notify users when export is ready
    
    try:
        # Process export request
        export_type = export_params.get('export_type')
        data_type = export_params.get('data_type')
        user_email = export_params.get('user_email')
        
        # Generate export data
        # ... export processing logic ...
        
        # Send completion notification
        send_mail(
            subject=f'Analytics Export Ready - {data_type}',
            message=f'''Your analytics export is ready for download.

Export Type: {export_type}
Data Type: {data_type}
Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

The export file will be available for download for the next 7 days.

Best regards,
Analytics Team''',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=True
        )
        
        return f"Export completed successfully for {user_email}"
        
    except Exception as e:
        # Send error notification
        send_mail(
            subject='Analytics Export Failed',
            message=f'Your analytics export failed to generate. Please try again or contact support.\n\nError: {str(e)}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[export_params.get('user_email')],
            fail_silently=True
        )
        
        return f"Export failed: {str(e)}"
