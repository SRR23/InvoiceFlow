"""
Serializers for User model and authentication.
"""
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User

# Loose bounds; service normalizes to exactly 6 digits.
OTP_INPUT_MIN_LEN = 4
OTP_INPUT_MAX_LEN = 32


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

    has_active_app_access = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'first_name',
            'last_name',
            'company_name',
            'phone',
            'currency',
            'is_business_user',
            'date_joined',
            'trial_ends_at',
            'subscription_status',
            'has_active_app_access',
        )
        read_only_fields = (
            'id',
            'email',
            'is_business_user',
            'date_joined',
            'trial_ends_at',
            'subscription_status',
            'has_active_app_access',
        )

    def get_has_active_app_access(self, obj: User) -> bool:
        return obj.has_active_app_access()


class PasswordResetRequestSerializer(serializers.Serializer):
    """Step 1: user submits account email to receive an OTP."""

    email = serializers.EmailField(required=True)


class PasswordResetVerifySerializer(serializers.Serializer):
    """Step 2: user submits email + OTP from the message."""

    email = serializers.EmailField(required=True)
    otp = serializers.CharField(
        required=True,
        trim_whitespace=True,
        min_length=OTP_INPUT_MIN_LEN,
        max_length=OTP_INPUT_MAX_LEN,
    )


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Step 3: user submits signed token from step 2 plus new password (twice)."""

    password_reset_token = serializers.CharField(required=True, write_only=True)
    password = serializers.CharField(required=True, write_only=True)
    password2 = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError(
                {"password": "Password fields didn't match."}
            )
        return attrs
