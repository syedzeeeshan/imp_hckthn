"""
URL patterns for events app
Complete endpoint routing for seamless API access
"""
from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    # Event Categories
    path('categories/', views.EventCategoryListView.as_view(), name='category_list'),
    
    # Event Listings and Search
    path('', views.EventListView.as_view(), name='event_list'),
    path('search/', views.search_events, name='search_events'),
    path('my-events/', views.my_events, name='my_events'),
    
    # Club-specific Events
    path('club/<slug:club_slug>/', views.ClubEventsView.as_view(), name='club_events'),
    
    # Event Details and Management
    path('<slug:slug>/', views.EventDetailView.as_view(), name='event_detail'),
    path('<slug:slug>/stats/', views.event_stats, name='event_stats'),
    
    # Event Registration
    path('<slug:slug>/register/', views.EventRegistrationView.as_view(), name='event_register'),
    path('<slug:slug>/unregister/', views.EventUnregisterView.as_view(), name='event_unregister'),
    
    # Event Attendees and Check-ins
    path('<slug:slug>/attendees/', views.EventAttendeesView.as_view(), name='event_attendees'),
    path('<slug:slug>/attendees/export/', views.export_attendees, name='export_attendees'),
    path('<slug:slug>/checkin/<str:registration_id>/', views.EventCheckInView.as_view(), name='event_checkin'),
    path('<slug:slug>/checkin/qr/', views.EventQRCheckInView.as_view(), name='event_qr_checkin'),
    path('<slug:slug>/checkin/bulk/', views.EventBulkCheckInView.as_view(), name='event_bulk_checkin'),
    
    # Event Feedback
    path('<slug:slug>/feedback/', views.EventFeedbackView.as_view(), name='event_feedback'),
]
