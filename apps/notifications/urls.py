"""
URL patterns for notifications app
Complete endpoint routing for notification system
"""
from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # Notification Types
    path('types/', views.NotificationTypeListView.as_view(), name='notification_types'),
    
    # User Settings
    path('settings/', views.NotificationSettingsView.as_view(), name='notification_settings'),
    path('preferences/', views.UpdateNotificationPreferencesView.as_view(), name='update_preferences'),
    
    # Notifications
    path('', views.NotificationListView.as_view(), name='notification_list'),
    path('<uuid:id>/', views.NotificationDetailView.as_view(), name='notification_detail'),
    path('create/', views.CreateNotificationView.as_view(), name='create_notification'),
    
    # Bulk Actions
    path('bulk-action/', views.BulkNotificationActionView.as_view(), name='bulk_action'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    
    # Push Devices
    path('devices/', views.PushDeviceView.as_view(), name='push_devices'),
    
    # Stats and Utilities
    path('stats/', views.notification_stats, name='notification_stats'),
    path('unread-count/', views.unread_count, name='unread_count'),
    path('test/', views.test_notification, name='test_notification'),
]
