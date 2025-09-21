"""
Authentication serializers for Campus Club Management Suite
API serialization for user registration, login, and profile management
"""
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User, College, UserProfile

class CollegeSerializer(serializers.ModelSerializer):
    """Serializer for College model"""
    
    total_users = serializers.ReadOnlyField()
    total_clubs = serializers.ReadOnlyField()
    
    class Meta:
        model = College
        fields = [
            'id', 'name', 'short_name', 'domain', 'official_email',
            'phone_number', 'website', 'address', 'city', 'state',
            'country', 'postal_code', 'is_verified', 'is_active',
            'logo', 'total_users', 'total_clubs', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'total_users', 'total_clubs']


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model"""
    
    class Meta:
        model = UserProfile
        fields = [
            'interests', 'skills', 'linkedin_url', 'twitter_url',
            'github_url', 'personal_website', 'notification_preferences',
            'privacy_settings', 'theme_preference', 'total_events_attended',
            'total_clubs_joined', 'total_collaborations', 'reputation_score'
        ]
        read_only_fields = [
            'total_events_attended', 'total_clubs_joined', 
            'total_collaborations', 'reputation_score'
        ]


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model with profile information"""
    
    profile = UserProfileSerializer(read_only=True)
    display_name = serializers.ReadOnlyField()
    permissions_level = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'full_name', 'display_name', 'user_type',
            'avatar', 'phone_number', 'date_of_birth', 'bio',
            'college_name', 'college_email_domain', 'student_id',
            'department', 'graduation_year', 'is_verified',
            'is_college_verified', 'is_active_member', 'last_activity',
            'google_id', 'github_id', 'profile', 'permissions_level',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'display_name', 'is_verified', 'is_college_verified',
            'verification_token', 'google_id', 'github_id', 'last_activity',
            'created_at', 'updated_at', 'permissions_level'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'full_name': {'required': True},
            'college_name': {'required': True},
        }
    
    def get_permissions_level(self, obj):
        return obj.get_permissions_level()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    college_domain = serializers.CharField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'email', 'password', 'password_confirm', 'full_name',
            'user_type', 'college_name', 'student_id', 'department',
            'graduation_year', 'phone_number', 'college_domain'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'full_name': {'required': True},
            'college_name': {'required': True},
            'password': {'write_only': True},
        }
    
    def validate_email(self, value):
        """Validate email format and domain"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists.")
        
        # Extract domain for college verification
        domain = value.split('@')[1] if '@' in value else ''
        
        # Check if domain belongs to a verified college
        college = College.objects.filter(domain=domain, is_verified=True).first()
        if not college:
            # For now, allow any domain but flag for verification
            pass
        
        return value
    
    def validate_user_type(self, value):
        """Validate user type based on permissions"""
        # Students can register as students or club leaders
        # Only existing admins can create new admins
        allowed_types = ['student', 'club_leader']
        
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if request.user.is_super_admin:
                allowed_types.extend(['college_admin', 'super_admin'])
            elif request.user.is_college_admin:
                allowed_types.append('college_admin')
        
        if value not in allowed_types:
            raise serializers.ValidationError(
                f"You don't have permission to create {value} accounts."
            )
        
        return value
    
    def validate(self, attrs):
        """Cross-field validation"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Password confirmation doesn't match.")
        
        # Remove password_confirm as it's not a model field
        attrs.pop('password_confirm')
        
        return attrs
    
    def create(self, validated_data):
        """Create new user with hashed password"""
        password = validated_data.pop('password')
        
        # Extract domain from email
        email = validated_data['email']
        domain = email.split('@')[1] if '@' in email else ''
        validated_data['college_email_domain'] = domain
        
        # Create user
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            **validated_data
        )
        
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        """Authenticate user credentials"""
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            # Authenticate using email as username
            user = authenticate(
                request=self.context.get('request'),
                username=email,
                password=password
            )
            
            if not user:
                raise serializers.ValidationError(
                    'Invalid email or password.',
                    code='authorization'
                )
            
            if not user.is_active:
                raise serializers.ValidationError(
                    'User account is disabled.',
                    code='authorization'
                )
            
            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError(
                'Must include "email" and "password".',
                code='authorization'
            )


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for password change"""
    
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)
    
    def validate_old_password(self, value):
        """Validate old password"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value
    
    def validate(self, attrs):
        """Validate password confirmation"""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("New password confirmation doesn't match.")
        return attrs


class PasswordResetSerializer(serializers.Serializer):
    """Serializer for password reset request"""
    
    email = serializers.EmailField()
    
    def validate_email(self, value):
        """Validate that user exists"""
        try:
            user = User.objects.get(email=value, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError("No active user found with this email.")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for password reset confirmation"""
    
    token = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    new_password_confirm = serializers.CharField()
    
    def validate(self, attrs):
        """Validate password confirmation"""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("Password confirmation doesn't match.")
        return attrs


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile"""
    
    profile = UserProfileSerializer(required=False)
    
    class Meta:
        model = User
        fields = [
            'full_name', 'avatar', 'phone_number', 'date_of_birth',
            'bio', 'student_id', 'department', 'graduation_year',
            'profile'
        ]
    
    def update(self, instance, validated_data):
        """Update user and profile data"""
        profile_data = validated_data.pop('profile', None)
        
        # Update user fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update profile fields
        if profile_data and hasattr(instance, 'profile'):
            profile = instance.profile
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()
        
        return instance
