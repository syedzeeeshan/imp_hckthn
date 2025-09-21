"""
Common permissions for Campus Club Management Suite
"""
from rest_framework import permissions

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed for any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner
        return obj.created_by == request.user

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow admins to edit it.
    """

    def has_permission(self, request, view):
        # Read permissions are allowed for any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to admin users.
        return request.user and request.user.is_staff

class IsClubMember(permissions.BasePermission):
    """
    Permission to check if user is a club member
    """
    
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'club'):
            return obj.club.memberships.filter(
                user=request.user, 
                status='active'
            ).exists()
        return False

class IsCollegeUser(permissions.BasePermission):
    """
    Permission to check if user belongs to the same college
    """
    
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'college'):
            return obj.college == request.user.college
        return True
