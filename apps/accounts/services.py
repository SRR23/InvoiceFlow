"""
Services for authentication and user management.
"""
import os
from django.conf import settings
from google.oauth2 import id_token
from google.auth.transport import requests
from google_auth_oauthlib.flow import Flow


class GoogleOAuthService:
    """Service for handling Google OAuth authentication."""
    
    # Google OAuth 2.0 scopes
    SCOPES = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']
    
    @staticmethod
    def get_authorization_url(redirect_uri):
        """
        Generate Google OAuth authorization URL.
        
        Args:
            redirect_uri: The callback URL where Google will redirect after authentication
            
        Returns:
            str: Authorization URL to redirect user to
        """
        client_id = os.environ.get('GOOGLE_CLIENT_ID')
        client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            raise ValueError('Google OAuth credentials not configured')
        
        # Create OAuth flow
        flow = Flow.from_client_config(
            {
                'web': {
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    'token_uri': 'https://oauth2.googleapis.com/token',
                    'redirect_uris': [redirect_uri]
                }
            },
            scopes=GoogleOAuthService.SCOPES,
            redirect_uri=redirect_uri
        )
        
        # Generate authorization URL
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        return authorization_url, state
    
    @staticmethod
    def verify_token_and_get_user_info(code, redirect_uri):
        """
        Exchange authorization code for user info.
        
        Args:
            code: Authorization code from Google callback
            redirect_uri: The callback URL (must match the one used in authorization)
            
        Returns:
            dict: User information from Google
        """
        client_id = os.environ.get('GOOGLE_CLIENT_ID')
        client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            raise ValueError('Google OAuth credentials not configured')
        
        # Create OAuth flow
        flow = Flow.from_client_config(
            {
                'web': {
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    'token_uri': 'https://oauth2.googleapis.com/token',
                    'redirect_uris': [redirect_uri]
                }
            },
            scopes=GoogleOAuthService.SCOPES,
            redirect_uri=redirect_uri
        )
        
        # Exchange code for token
        flow.fetch_token(code=code)
        
        # Get credentials
        credentials = flow.credentials
        
        # Verify ID token and get user info
        request = requests.Request()
        idinfo = id_token.verify_oauth2_token(
            credentials.id_token,
            request,
            client_id
        )
        
        # Verify the token is for the correct user
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Wrong issuer.')
        
        return {
            'google_id': idinfo['sub'],
            'email': idinfo['email'],
            'first_name': idinfo.get('given_name', ''),
            'last_name': idinfo.get('family_name', ''),
            'picture': idinfo.get('picture', ''),
            'verified_email': idinfo.get('email_verified', False),
        }
