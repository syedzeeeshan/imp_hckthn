"""
Authentication views for Campus Club Management Suite
API views for user registration, login, profile management, and college verification
"""
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import login, logout
from django.core.mail import send_mail
from django.conf import settings
from django.utils.crypto import get_random_string
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from .models import User, College, UserProfile
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, UserSerializer,
    CollegeSerializer, UserUpdateSerializer, PasswordChangeSerializer,
    PasswordResetSerializer, PasswordResetConfirmSerializer
)
from apps.common.permissions import IsOwnerOrReadOnly, IsAdminOrReadOnly

class UserRegistrationView(generics.CreateAPIView):
    """User registration endpoint"""
    
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate verification token
        verification_token = get_random_string(32)
        user.verification_token = verification_token
        user.save()
        
        # Send verification email
        self.send_verification_email(user, verification_token)
        
        # Create auth token
        token, created = Token.objects.get_or_create(user=user)
        
        # Serialize user data
        user_serializer = UserSerializer(user)
        
        return Response({
            'message': 'Registration successful. Please check your email for verification.',
            'user': user_serializer.data,
            'token': token.key,
            'token_type': 'Token'
        }, status=status.HTTP_201_CREATED)
    
    def send_verification_email(self, user, token):
        """Send email verification"""
        try:
            verification_url = f"{settings.FRONTEND_URL}/verify-email/{token}/"
            
            subject = 'Welcome to Campus Club Management Suite - Verify Your Email'
            message = f"""
            Welcome {user.full_name}!
            
            Thank you for joining Campus Club Management Suite. Please verify your email address by clicking the link below:
            
            {verification_url}
            
            If you didn't create this account, please ignore this email.
            
            Best regards,
            Campus Club Management Team
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True
            )
        except Exception as e:
            print(f"Failed to send verification email: {e}")


class UserLoginView(APIView):
    """User login endpoint"""
    
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        
        # Update last activity
        user.last_activity = timezone.now()
        user.save(update_fields=['last_activity'])
        
        # Get or create auth token
        token, created = Token.objects.get_or_create(user=user)
        
        # Serialize user data
        user_serializer = UserSerializer(user)
        
        return Response({
            'message': 'Login successful',
            'user': user_serializer.data,
            'token': token.key,
            'token_type': 'Token'
        }, status=status.HTTP_200_OK)


class UserLogoutView(APIView):
    """User logout endpoint"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            # Delete the token
            request.user.auth_token.delete()
            return Response({
                'message': 'Successfully logged out'
            }, status=status.HTTP_200_OK)
        except Token.DoesNotExist:
            return Response({
                'message': 'User was not logged in'
            }, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """User profile view and update"""
    
    serializer_class = UserUpdateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user


class UserDetailView(generics.RetrieveAPIView):
    """Get user details by ID"""
    
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Users can only see verified users or users from same college
        user = self.request.user
        
        if user.is_super_admin:
            return User.objects.all()
        elif user.is_college_admin:
            return User.objects.filter(college_email_domain=user.college_email_domain)
        else:
            return User.objects.filter(
                Q(is_verified=True) | 
                Q(college_email_domain=user.college_email_domain)
            )


class UserListView(generics.ListAPIView):
    """List all users with filtering"""
    
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.is_super_admin:
            queryset = User.objects.all()
        elif user.is_college_admin:
            queryset = User.objects.filter(college_email_domain=user.college_email_domain)
        else:
            queryset = User.objects.filter(is_verified=True)
        
        # Apply filters
        college = self.request.query_params.get('college')
        user_type = self.request.query_params.get('user_type')
        search = self.request.query_params.get('search')
        
        if college:
            queryset = queryset.filter(college_name__icontains=college)
        
        if user_type:
            queryset = queryset.filter(user_type=user_type)
        
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) |
                Q(email__icontains=search) |
                Q(college_name__icontains=search)
            )
        
        return queryset.distinct()


class PasswordChangeView(APIView):
    """Change user password"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        return Response({
            'message': 'Password changed successfully'
        }, status=status.HTTP_200_OK)


class PasswordResetView(APIView):
    """Request password reset"""
    
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        user = User.objects.get(email=email)
        
        # Generate reset token
        reset_token = get_random_string(32)
        user.verification_token = reset_token
        user.save()
        
        # Send reset email
        self.send_reset_email(user, reset_token)
        
        return Response({
            'message': 'Password reset email sent'
        }, status=status.HTTP_200_OK)
    
    def send_reset_email(self, user, token):
        """Send password reset email"""
        try:
            reset_url = f"{settings.FRONTEND_URL}/reset-password/{token}/"
            
            subject = 'Reset Your Password - Campus Club Management Suite'
            message = f"""
            Hello {user.full_name},
            
            You requested to reset your password for Campus Club Management Suite.
            
            Click the link below to reset your password:
            {reset_url}
            
            This link will expire in 24 hours.
            
            If you didn't request this reset, please ignore this email.
            
            Best regards,
            Campus Club Management Team
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True
            )
        except Exception as e:
            print(f"Failed to send reset email: {e}")


class PasswordResetConfirmView(APIView):
    """Confirm password reset with token"""
    
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']
        
        try:
            user = User.objects.get(verification_token=token)
            
            # Check if token is not too old (24 hours)
            token_age = timezone.now() - user.updated_at
            if token_age > timedelta(hours=24):
                return Response({
                    'error': 'Reset token has expired'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Reset password
            user.set_password(new_password)
            user.verification_token = ''  # Clear token
            user.save()
            
            return Response({
                'message': 'Password reset successfully'
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response({
                'error': 'Invalid reset token'
            }, status=status.HTTP_400_BAD_REQUEST)


class EmailVerificationView(APIView):
    """Verify user email with token"""
    
    permission_classes = [AllowAny]
    
    def post(self, request):
        token = request.data.get('token')
        
        if not token:
            return Response({
                'error': 'Verification token is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(verification_token=token)
            
            if user.is_verified:
                return Response({
                    'message': 'Email already verified'
                }, status=status.HTTP_200_OK)
            
            # Verify email
            user.is_verified = True
            user.verification_token = ''
            
            # Check college verification
            college = College.objects.filter(
                domain=user.college_email_domain, 
                is_verified=True
            ).first()
            
            if college:
                user.is_college_verified = True
            
            user.save()
            
            return Response({
                'message': 'Email verified successfully',
                'is_college_verified': user.is_college_verified
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response({
                'error': 'Invalid verification token'
            }, status=status.HTTP_400_BAD_REQUEST)


class CollegeListView(generics.ListCreateAPIView):
    """List and create colleges"""
    
    queryset = College.objects.all()
    serializer_class = CollegeSerializer
    
    def get_permissions(self):
        """Only admins can create colleges"""
        if self.request.method == 'POST':
            self.permission_classes = [IsAuthenticated]
        else:
            self.permission_classes = [AllowAny]
        return super().get_permissions()
    
    def perform_create(self, serializer):
        """Only super admins can create colleges"""
        if not self.request.user.is_super_admin:
            raise permissions.PermissionDenied("Only super admins can create colleges")
        serializer.save()


class CollegeDetailView(generics.RetrieveUpdateDestroyAPIView):
    """College detail, update, and delete"""
    
    queryset = College.objects.all()
    serializer_class = CollegeSerializer
    permission_classes = [IsAdminOrReadOnly]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    """Get current authenticated user details"""
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def check_email_availability(request):
    """Check if email is available for registration"""
    email = request.query_params.get('email')
    
    if not email:
        return Response({
            'error': 'Email parameter is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    is_available = not User.objects.filter(email=email).exists()
    
    # Check college domain
    domain = email.split('@')[1] if '@' in email else ''
    college = College.objects.filter(domain=domain, is_verified=True).first()
    
    return Response({
        'available': is_available,
        'college_verified': bool(college),
        'college_name': college.name if college else None
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def resend_verification_email(request):
    """Resend email verification"""
    user = request.user
    
    if user.is_verified:
        return Response({
            'message': 'Email is already verified'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Generate new token
    verification_token = get_random_string(32)
    user.verification_token = verification_token
    user.save()
    
    # Send email (reuse logic from registration)
    try:
        verification_url = f"{settings.FRONTEND_URL}/verify-email/{verification_token}/"
        
        subject = 'Verify Your Email - Campus Club Management Suite'
        message = f"""
        Hello {user.full_name},
        
        Please verify your email address by clicking the link below:
        
        {verification_url}
        
        Best regards,
        Campus Club Management Team
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False
        )
        
        return Response({
            'message': 'Verification email sent successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': 'Failed to send verification email'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_stats(request):
    """Get user statistics for dashboard"""
    user = request.user
    
    # Get user stats
    if hasattr(user, 'profile'):
        profile = user.profile
        stats = {
            'total_events_attended': profile.total_events_attended,
            'total_clubs_joined': profile.total_clubs_joined,
            'total_collaborations': profile.total_collaborations,
            'reputation_score': profile.reputation_score,
        }
    else:
        stats = {
            'total_events_attended': 0,
            'total_clubs_joined': 0,
            'total_collaborations': 0,
            'reputation_score': 0,
        }
    
    # Add recent activity
    stats['last_activity'] = user.last_activity
    stats['member_since'] = user.created_at
    stats['is_verified'] = user.is_verified
    stats['is_college_verified'] = user.is_college_verified
    
    return Response(stats)
