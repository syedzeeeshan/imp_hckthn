"""
URL patterns for clubs app
"""
from django.urls import path
from . import views

app_name = 'clubs'

urlpatterns = [
    # Categories
    path('categories/', views.ClubCategoryListView.as_view(), name='category_list'),
    
    # Clubs
    path('', views.ClubListView.as_view(), name='club_list'),
    path('create/', views.ClubCreateView.as_view(), name='club_create'),
    path('my-clubs/', views.my_clubs, name='my_clubs'),
    path('search/', views.search_clubs, name='search_clubs'),
    
    # Club detail and management
    path('<slug:slug>/', views.ClubDetailView.as_view(), name='club_detail'),
    path('<slug:slug>/join/', views.JoinClubView.as_view(), name='join_club'),
    path('<slug:slug>/leave/', views.LeaveClubView.as_view(), name='leave_club'),
    path('<slug:slug>/stats/', views.club_stats, name='club_stats'),
    
    # Members
    path('<slug:slug>/members/', views.ClubMembersView.as_view(), name='club_members'),
    path('<slug:slug>/members/<str:membership_id>/manage/', views.ManageMembershipView.as_view(), name='manage_membership'),
    
    # Announcements
    path('<slug:slug>/announcements/', views.ClubAnnouncementsView.as_view(), name='club_announcements'),
]
