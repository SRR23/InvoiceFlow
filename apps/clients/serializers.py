"""
Serializers for Client model.
"""
from rest_framework import serializers
from .models import Client


class ClientSerializer(serializers.ModelSerializer):
    """Serializer for Client model."""
    
    class Meta:
        model = Client
        fields = ('id', 'name', 'email', 'phone', 'company', 'address', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')
