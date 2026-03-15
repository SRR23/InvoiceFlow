"""
Serializers for User model and authentication.
"""
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True, label='Confirm Password')
    
    class Meta:
        model = User
        fields = ('email', 'password', 'password2', 'first_name', 'last_name', 'company_name', 'phone', 'currency')
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
            'company_name': {'required': False},
            'phone': {'required': False},
        }
    
    def validate(self, attrs):
        """Validate that passwords match."""
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs
    
    def create(self, validated_data):
        """Create a new user."""
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True, style={'input_type': 'password'})

class LogoutSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(
        required=True,
        help_text="JWT refresh token to blacklist",
        style={'input_type': 'password'},  # This hides it in browsable API
        write_only=True
    )

    
class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile."""
    
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'company_name', 'phone', 'currency', 'is_business_user', 'date_joined')
        read_only_fields = ('id', 'email', 'is_business_user', 'date_joined')
