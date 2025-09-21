"""
URL patterns for authentication app
"""
from django.urls import path
from . import views

app_name = 'authentication'

urlpatterns = [
    # Authentication endpoints
    path('register/', views.UserRegistrationView.as_view(), name='register'),
    path('login/', views.UserLoginView.as_view(), name='login'),
    path('logout/', views.UserLogoutView.as_view(), name='logout'),
    
    # Email verification
    path('verify-email/', views.EmailVerificationView.as_view(), name='verify_email'),
    path('resend-verification/', views.resend_verification_email, name='resend_verification'),
    
    # Password management
    path('change-password/', views.PasswordChangeView.as_view(), name='change_password'),
    path('reset-password/', views.PasswordResetView.as_view(), name='reset_password'),
    path('reset-password/confirm/', views.PasswordResetConfirmView.as_view(), name='reset_password_confirm'),
    
    # User management
    path('me/', views.current_user, name='current_user'),
    path('profile/', views.UserProfileView.as_view(), name='user_profile'),
    path('stats/', views.user_stats, name='user_stats'),
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/<uuid:pk>/', views.UserDetailView.as_view(), name='user_detail'),
    
    # Utilities
    path('check-email/', views.check_email_availability, name='check_email'),
    
    # Colleges
    path('colleges/', views.CollegeListView.as_view(), name='college_list'),
    path('colleges/<uuid:pk>/', views.CollegeDetailView.as_view(), name='college_detail'),
]
