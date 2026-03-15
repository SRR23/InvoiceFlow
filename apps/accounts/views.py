"""
Authentication views for user registration, login, and profile management.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from drf_spectacular.utils import (
    extend_schema, 
    OpenApiResponse, 
    OpenApiRequest, 
    OpenApiExample
)
from .models import User
from .serializers import (
    UserRegistrationSerializer, 
    UserProfileSerializer, 
    LoginSerializer,
    LogoutSerializer
)
from .services.google_auth import (
    verify_google_id_token,
    get_or_create_google_user,
    generate_jwt_for_user
)

import logging
logger = logging.getLogger(__name__)


@extend_schema(
    tags=['Authentication'],
    summary='Register a new user',
    description='Create a new business user account. Returns JWT tokens for authentication.',
    request=UserRegistrationSerializer,
    responses={
        201: OpenApiResponse(description='User successfully created with JWT tokens'),
        400: OpenApiResponse(description='Validation error'),
    }
)
class RegisterView(APIView):
    """User registration endpoint."""
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserProfileSerializer(user).data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
        }, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["Authentication"],
    summary="User Login",
    description="Authenticate user using email and password. Returns JWT tokens.",
    request=LoginSerializer,  # ← Use the serializer here
    responses={
        200: OpenApiResponse(description="Login successful"),
        400: OpenApiResponse(description="Missing email or password"),
        401: OpenApiResponse(description="Invalid credentials"),
        403: OpenApiResponse(description="User account disabled"),
    },
)
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # You can also use the serializer for validation if you want
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data.get("email")
        password = serializer.validated_data.get("password")

        user = User.objects.filter(email=email).first()

        if not user or not user.check_password(password):
            return Response(
                {"detail": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"detail": "User account is disabled"},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "user": UserProfileSerializer(user).data,
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Authentication"],
    summary="Google Login with ID Token",
    description=(
        "Authenticate user using Google ID token (JWT).\n\n"
        "Frontend should use `@react-oauth/google` or Google Identity Services to get the `credential` "
        "(ID token), then send it to this endpoint.\n\n"
        "This endpoint verifies the token, creates or logs in the user, and returns JWT access + refresh tokens."
    ),
    request=OpenApiRequest(
        request={
            "type": "object",
            "properties": {
                "id_token": {
                    "type": "string",
                    "description": "Google ID token (JWT) obtained from Google Sign-In",
                    "example": "eyJhbGciOiJSUzI1NiIsImtpZCI6IjEyMzQ1Njc4OTAiLCJ0eXAiOiJKV1QifQ..."
                }
            },
            "required": ["id_token"]
        }
    ),
    responses={
        200: OpenApiResponse(
            description="Successful authentication",
            response={
                "type": "object",
                "properties": {
                    "user": {
                        "type": "object",
                        # Use $ref if you have a component schema for UserProfile
                        # "$ref": "#/components/schemas/UserProfile"
                        # Or keep inline:
                        "properties": {
                            "id": {"type": "integer"},
                            "email": {"type": "string"},
                            "first_name": {"type": "string", "nullable": True},
                            "last_name": {"type": "string", "nullable": True},
                            "is_business_user": {"type": "boolean"},
                            "google_id": {"type": "string", "nullable": True},
                            # Add more fields from your UserProfileSerializer as needed
                        }
                    },
                    "access": {
                        "type": "string",
                        "description": "JWT access token (short-lived)",
                        "example": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                    },
                    "refresh": {
                        "type": "string",
                        "description": "JWT refresh token (long-lived)",
                        "example": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                    }
                },
                "required": ["user", "access", "refresh"]
            },
            examples=[
                OpenApiExample(
                    "Success Response",
                    value={
                        "user": {
                            "id": 42,
                            "email": "user@example.com",
                            "first_name": "Shaidur",
                            "last_name": "",
                            "is_business_user": True,
                            "google_id": "123456789012345678901"
                        },
                        "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                    },
                    summary="Example of successful Google login",
                    description="User was found/created and JWT tokens issued.",
                    status_codes=['200'],  # ← FIXED HERE (string or int, list/tuple allowed)
                    response_only=True,     # optional but good practice
                )
            ]
        ),
        400: OpenApiResponse(
            description="Invalid or missing ID token",
            response={
                "type": "object",
                "properties": {
                    "detail": {"type": "string"}
                },
                "examples": [  # you can also use OpenApiExample here if you want named examples
                    {"detail": "id_token is required"},
                    {"detail": "Invalid Google ID token: Token expired"},
                    {"detail": "Invalid Google ID token: Wrong audience"},
                ]
            }
        ),
        500: OpenApiResponse(
            description="Server error during authentication",
            response={"type": "object", "properties": {"detail": {"type": "string"}}}
        )
    }
)
class GoogleLoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        id_token_str = request.data.get('id_token')

        if not id_token_str:
            return Response({"detail": "id_token is required"}, status=400)

        try:
            logger.info(f"Received ID token (first 50 chars): {id_token_str[:50]}...")
            
            idinfo = verify_google_id_token(id_token_str)
            logger.info(f"Verified claims: {idinfo.keys()}")
            
            user, created = get_or_create_google_user(idinfo)
            tokens = generate_jwt_for_user(user)

            return Response({
                "user": UserProfileSerializer(user).data,
                "tokens": { 
                    "access": tokens['access'],
                    "refresh": tokens['refresh'],
                },
            })

        except ValueError as ve:
            logger.error(f"Google token verification failed: {str(ve)}", exc_info=True)
            return Response(
                {"detail": f"Invalid Google token: {str(ve)}"},
                status=400
            )
        except Exception as e:
            logger.exception("Unexpected error in Google login")
            return Response(
                {"detail": f"Server error: {str(e)}"},
                status=500
            )
        

@extend_schema(
    tags=["Authentication"],
    summary="User Logout",
    description="Logout user by blacklisting refresh token.",
    request=LogoutSerializer,  # ← Use the serializer here
    responses={
        200: OpenApiResponse(
            description="Logout successful",
            response={"type": "object", "properties": {"detail": {"type": "string"}}}
        ),
        400: OpenApiResponse(
            description="Invalid refresh token or token not provided",
            response={"type": "object", "properties": {"detail": {"type": "string"}}}
        ),
    },
)
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Use serializer for validation
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        refresh_token = serializer.validated_data.get("refresh_token")

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response(
                {"detail": "Successfully logged out"},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            # You might want to log the actual error
            # logger.error(f"Logout error: {str(e)}")
            return Response(
                {"detail": "Invalid refresh token"},
                status=status.HTTP_400_BAD_REQUEST,
            )



@extend_schema(
    tags=['Authentication'],
    summary='Get user profile',
    description='Retrieve the authenticated user\'s profile information.',
    responses={200: UserProfileSerializer}
)
class UserProfileView(APIView):
    """User profile view and update endpoint."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get user profile."""
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)
    
    @extend_schema(
        tags=['Authentication'],
        summary='Update user profile',
        description='Update the authenticated user\'s profile information.',
        request=UserProfileSerializer,
        responses={200: UserProfileSerializer}
    )
    def patch(self, request):
        """Update user profile."""
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    @extend_schema(
        tags=['Authentication'],
        summary='Update user profile (full)',
        description='Update all fields of the authenticated user\'s profile.',
        request=UserProfileSerializer,
        responses={200: UserProfileSerializer}
    )
    def put(self, request):
        """Update user profile (full update)."""
        serializer = UserProfileSerializer(request.user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
