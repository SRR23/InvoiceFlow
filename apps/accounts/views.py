"""
Authentication views for user registration, login, and profile management.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from .models import User
from .serializers import UserRegistrationSerializer, UserProfileSerializer


@extend_schema(
    tags=['Authentication'],
    summary='Register a new user',
    description='Create a new business user account. Returns JWT tokens for authentication.',
    request=UserRegistrationSerializer,
    responses={
        201: OpenApiResponse(
            description='User successfully created',
            response={
                'type': 'object',
                'properties': {
                    'user': UserProfileSerializer,
                    'tokens': {
                        'type': 'object',
                        'properties': {
                            'refresh': {'type': 'string'},
                            'access': {'type': 'string'},
                        }
                    }
                }
            }
        ),
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
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['Authentication'],
    summary='User login',
    description='Authenticate user with email and password. Returns JWT tokens.',
    request={
        'type': 'object',
        'properties': {
            'email': {'type': 'string', 'format': 'email'},
            'password': {'type': 'string', 'format': 'password'},
        },
        'required': ['email', 'password']
    },
    responses={
        200: OpenApiResponse(
            description='Login successful',
            response={
                'type': 'object',
                'properties': {
                    'user': UserProfileSerializer,
                    'tokens': {
                        'type': 'object',
                        'properties': {
                            'refresh': {'type': 'string'},
                            'access': {'type': 'string'},
                        }
                    }
                }
            }
        ),
        400: OpenApiResponse(description='Email and password are required'),
        401: OpenApiResponse(description='Invalid credentials'),
        403: OpenApiResponse(description='User account is disabled'),
    }
)
class LoginView(APIView):
    """User login endpoint with email and password."""
    permission_classes = [AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not email or not password:
            return Response(
                {'error': 'Email and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = authenticate(request, username=email, password=password)
        
        if not user:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.is_active:
            return Response(
                {'error': 'User account is disabled'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserProfileSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        })


@extend_schema(
    tags=['Authentication'],
    summary='Google OAuth login',
    description='Authenticate user with Google OAuth. Returns JWT tokens.',
    request={
        'type': 'object',
        'properties': {
            'google_id': {'type': 'string'},
            'email': {'type': 'string', 'format': 'email'},
            'first_name': {'type': 'string'},
            'last_name': {'type': 'string'},
        },
        'required': ['google_id', 'email']
    },
    responses={
        200: OpenApiResponse(
            description='Login successful',
            response={
                'type': 'object',
                'properties': {
                    'user': UserProfileSerializer,
                    'tokens': {
                        'type': 'object',
                        'properties': {
                            'refresh': {'type': 'string'},
                            'access': {'type': 'string'},
                        }
                    }
                }
            }
        ),
        400: OpenApiResponse(description='Google ID and email are required'),
    }
)
class GoogleLoginView(APIView):
    """Google OAuth login endpoint."""
    permission_classes = [AllowAny]
    
    def post(self, request):
        # TODO: Implement Google OAuth verification
        # For now, this is a placeholder
        google_id = request.data.get('google_id')
        email = request.data.get('email')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')
        
        if not google_id or not email:
            return Response(
                {'error': 'Google ID and email are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get or create user
        user, created = User.objects.get_or_create(
            google_id=google_id,
            defaults={
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'is_business_user': True,
            }
        )
        
        if not created:
            # Update user info if exists
            user.email = email
            user.first_name = first_name
            user.last_name = last_name
            user.save()
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserProfileSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        })


@extend_schema(
    tags=['Authentication'],
    summary='User logout',
    description='Logout user and blacklist refresh token.',
    request={
        'type': 'object',
        'properties': {
            'refresh_token': {'type': 'string'},
        }
    },
    responses={
        200: OpenApiResponse(description='Successfully logged out'),
        400: OpenApiResponse(description='Invalid refresh token'),
    }
)
class LogoutView(APIView):
    """User logout endpoint."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({'message': 'Successfully logged out'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


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
