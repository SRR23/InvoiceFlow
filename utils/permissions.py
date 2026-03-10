"""
Custom permissions for the InvoiceFlow API.
"""
from rest_framework import permissions


class IsBusinessUser(permissions.BasePermission):
    """
    Permission to check if user is a business user.
    Only business users can access business APIs.
    """
    message = "Only business users can access this resource."
    
    def has_permission(self, request, view):
        """Check if user is authenticated and is a business user."""
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_business_user
        )


class IsOwner(permissions.BasePermission):
    """
    Permission to check if user owns the resource.
    """
    message = "You do not have permission to access this resource."
    
    def has_object_permission(self, request, view, obj):
        """Check if the user owns the object."""
        # Check if object has a user attribute
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # Check if object has a user_id attribute
        if hasattr(obj, 'user_id'):
            return obj.user_id == request.user.id
        
        # For related objects (e.g., invoice items)
        if hasattr(obj, 'invoice'):
            return obj.invoice.user == request.user
        
        return False
