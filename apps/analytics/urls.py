"""
URL patterns for analytics app
"""
from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard_overview, name='dashboard_overview'),
    path('reports/', views.AnalyticsReportListView.as_view(), name='reports_list'),
    path('reports/<uuid:pk>/', views.AnalyticsReportDetailView.as_view(), name='report_detail'),
    path('charts/', views.chart_data, name='charts_data'),
    path('stats/', views.dashboard_overview, name='platform_stats'), # Assuming this should also point to the overview
    path('export/', views.export_analytics, name='export_data'),
]
