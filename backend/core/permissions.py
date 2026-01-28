"""
Custom permissions for the timetable system.
"""
from rest_framework import permissions


class IsMasterAdmin(permissions.BasePermission):
    """Permission check for Master Admin."""
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == 'master_admin'
        )


class IsCollegeAdminOrMaster(permissions.BasePermission):
    """Permission check for College Admin or Master Admin."""
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in ['master_admin', 'college_admin']
        )


class IsCollegeMember(permissions.BasePermission):
    """Permission check for any college member."""
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.college is not None
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    """Permission to allow owners or admins."""
    def has_object_permission(self, request, view, obj):
        # Master admin can do anything
        if request.user.role == 'master_admin':
            return True
        
        # College admin can manage their college's resources
        if request.user.role == 'college_admin' and hasattr(obj, 'college'):
            return obj.college == request.user.college
        
        # Users can manage their own resources
        if hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        
        return False
