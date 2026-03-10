"""
Views for Client management.
"""
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from utils.permissions import IsBusinessUser, IsOwner
from .models import Client
from .serializers import ClientSerializer


class ClientViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing clients.
    Only business users can access their own clients.
    """
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated, IsBusinessUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['name', 'email', 'company']
    search_fields = ['name', 'email', 'company', 'phone']
    ordering_fields = ['created_at', 'name']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return only clients belonging to the current user."""
        return Client.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Set the user when creating a new client."""
        serializer.save(user=self.request.user)
