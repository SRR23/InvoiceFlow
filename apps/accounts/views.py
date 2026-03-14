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
        200: OpenApiResponse(description='Login successful, returns user data and JWT tokens'),
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
    summary='Get Google OAuth URL',
    description='Get Google OAuth authorization URL. User should be redirected to this URL to start OAuth flow.',
    responses={
        200: OpenApiResponse(
            description='Google OAuth authorization URL',
            response={
                'type': 'object',
                'properties': {
                    'authorization_url': {'type': 'string', 'format': 'uri'},
                }
            }
        ),
        500: OpenApiResponse(description='Google OAuth not configured'),
    }
)
class GoogleOAuthURLView(APIView):
    """Get Google OAuth authorization URL."""
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Return Google OAuth authorization URL."""
        from django.conf import settings
        from apps.accounts.services import GoogleOAuthService
        
        try:
            # Construct backend callback URL
            # This should be the backend URL, not frontend
            scheme = request.scheme
            host = request.get_host()
            callback_url = f"{scheme}://{host}/api/auth/google/callback/"
            
            # Get frontend redirect URI from query params (where to redirect after auth)
            frontend_redirect = request.query_params.get('redirect_uri', settings.FRONTEND_URL)
            
            authorization_url, state = GoogleOAuthService.get_authorization_url(callback_url)
            
            # Store frontend redirect in session or return it to be stored by frontend
            return Response({
                'authorization_url': authorization_url,
                'state': state,
                'frontend_redirect': frontend_redirect,
            })
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(
    tags=['Authentication'],
    summary='Google OAuth callback',
    description='Handle Google OAuth callback. Creates user if new, logs in if existing. Returns JWT tokens.',
    parameters=[
        OpenApiParameter(
            name='code',
            type=str,
            location=OpenApiParameter.QUERY,
            description='Authorization code from Google',
            required=True,
        ),
        OpenApiParameter(
            name='state',
            type=str,
            location=OpenApiParameter.QUERY,
            description='State parameter from OAuth flow',
            required=False,
        ),
        OpenApiParameter(
            name='redirect_uri',
            type=str,
            location=OpenApiParameter.QUERY,
            description='Frontend URL to redirect to after authentication',
            required=False,
        ),
        OpenApiParameter(
            name='format',
            type=str,
            location=OpenApiParameter.QUERY,
            description='Response format: "json" for JSON response, default is redirect',
            required=False,
        ),
    ],
    responses={
        200: OpenApiResponse(description='Login/Signup successful, returns user data and JWT tokens'),
        400: OpenApiResponse(description='Invalid authorization code'),
        500: OpenApiResponse(description='OAuth verification failed'),
    }
)
class GoogleOAuthCallbackView(APIView):
    """Handle Google OAuth callback and authenticate user."""
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Process Google OAuth callback and authenticate user."""
        from django.conf import settings
        from apps.accounts.services import GoogleOAuthService
        
        code = request.query_params.get('code')
        if not code:
            return Response(
                {'error': 'Authorization code is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Construct backend callback URL (must match the one used in authorization)
            scheme = request.scheme
            host = request.get_host()
            callback_url = f"{scheme}://{host}/api/auth/google/callback/"
            
            # Verify token and get user info
            user_info = GoogleOAuthService.verify_token_and_get_user_info(code, callback_url)
            
            # Get or create user
            user, created = User.objects.get_or_create(
                google_id=user_info['google_id'],
                defaults={
                    'email': user_info['email'],
                    'first_name': user_info['first_name'],
                    'last_name': user_info['last_name'],
                    'is_business_user': True,
                }
            )
            
            # Update user info if exists (in case name changed)
            if not created:
                user.email = user_info['email']
                user.first_name = user_info['first_name']
                user.last_name = user_info['last_name']
                user.save()
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            # Get frontend redirect URL from query params
            frontend_redirect = request.query_params.get('redirect_uri', settings.FRONTEND_URL)
            
            # Option 1: Return JSON response (for API clients)
            if request.query_params.get('format') == 'json':
                return Response({
                    'user': UserProfileSerializer(user).data,
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    },
                    'is_new_user': created,
                })
            
            # Option 2: Redirect to frontend with tokens in URL (for web browsers)
            # Frontend should extract tokens from URL and store them
            from urllib.parse import urlencode
            tokens = {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
            redirect_url = f"{frontend_redirect}?{urlencode(tokens)}"
            
            from django.shortcuts import redirect
            return redirect(redirect_url)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'OAuth verification failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
