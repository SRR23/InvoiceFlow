"""
Custom permissions for the InvoiceFlow API.
"""
from rest_framework import permissions


class IsBusinessUser(permissions.BasePermission):
    """
    Permission for business APIs: must be a business user, and either in the free trial
    window or on an active-enough Stripe SaaS subscription (staff/superuser exempt).
    """
    message = "Only business users can access this resource."

    def has_permission(self, request, view):
        self.message = "Only business users can access this resource."
        if not (request.user and request.user.is_authenticated and request.user.is_business_user):
            return False
        if request.user.is_staff or request.user.is_superuser:
            return True
        if not request.user.has_active_app_access():
            self.message = (
                "Your trial has ended or your subscription is inactive. "
                "Subscribe to continue using InvoiceFlow."
            )
            return False
        return True


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
