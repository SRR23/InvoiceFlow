
from rest_framework import serializers
from .models import Client


class ClientSerializer(serializers.ModelSerializer):
    """Serializer for Client model."""
    
    class Meta:
        model = Client
        fields = ('id', 'name', 'email', 'phone', 'company', 'address', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')


class ClientImportRowErrorSerializer(serializers.Serializer):
    row = serializers.IntegerField()
    message = serializers.CharField()


class ClientImportSkipSerializer(serializers.Serializer):
    row = serializers.IntegerField()
    email = serializers.CharField(allow_blank=True, required=False)
    message = serializers.CharField()


class ClientImportResultSerializer(serializers.Serializer):
    created = serializers.IntegerField()
    had_no_data_rows = serializers.BooleanField()
    message = serializers.CharField(allow_null=True, required=False)
    skipped_duplicate_in_file = ClientImportSkipSerializer(many=True)
    skipped_existing_email = ClientImportSkipSerializer(many=True)
    row_errors = ClientImportRowErrorSerializer(many=True)
