"""
URL patterns for collaboration app
Complete endpoint routing for inter-college partnerships
"""
from django.urls import path
from . import views

app_name = 'collaboration'

urlpatterns = [
    # Collaboration Types
    path('types/', views.CollaborationTypeListView.as_view(), name='type_list'),
    
    # Collaboration Listings and Search
    path('', views.CollaborationListView.as_view(), name='collaboration_list'),
    path('search/', views.search_collaborations, name='search_collaborations'),
    path('my-collaborations/', views.my_collaborations, name='my_collaborations'),
    
    # Club-specific Collaborations
    path('club/<slug:club_slug>/', views.ClubCollaborationsView.as_view(), name='club_collaborations'),
    
    # Collaboration Details and Management
    path('<slug:slug>/', views.CollaborationDetailView.as_view(), name='collaboration_detail'),
    path('<slug:slug>/stats/', views.collaboration_stats, name='collaboration_stats'),
    
    # Collaboration Applications
    path('<slug:slug>/apply/<slug:club_slug>/', views.CollaborationApplicationView.as_view(), name='apply_collaboration'),
    
    # Participation Management
    path('<slug:slug>/participants/', views.CollaborationParticipantsView.as_view(), name='collaboration_participants'),
    path('<slug:slug>/participants/<uuid:participation_id>/manage/', views.ManageParticipationView.as_view(), name='manage_participation'),
]
