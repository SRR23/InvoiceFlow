
from google.oauth2 import id_token
from google.auth.transport import requests
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from ..models import User

def verify_google_id_token(token: str) -> dict:
    """
    Verify Google ID token (JWT) securely.
    Returns decoded claims or raises ValueError.
    """
    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            settings.GOOGLE_CLIENT_ID
        )

        # Extra security checks
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError("Invalid issuer")
        
        if not idinfo.get('email_verified'):
            raise ValueError("Email not verified by Google")

        return idinfo

    except ValueError as e:
        raise ValueError(f"Invalid Google ID token: {str(e)}")


def get_or_create_google_user(idinfo: dict) -> tuple[User, bool]:
    """
    Get or create user based on Google email + sub (google_id).
    """
    email = idinfo['email']
    google_id = idinfo['sub']

    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            # 'username': email,  # or generate random if you prefer
            'first_name': idinfo.get('given_name', ''),
            'last_name': idinfo.get('family_name', ''),
            'google_id': google_id,
            'is_business_user': True,  # ← your custom logic
            # avatar = models.URLField(blank=True) → add if you have this field
            # user.avatar = idinfo.get('picture', '')
        }
    )

    if not created:
        # Optional: update fields if changed on Google
        updated = False
        if user.google_id != google_id:
            user.google_id = google_id
            updated = True
        # if user.avatar != idinfo.get('picture'):
        #     user.avatar = idinfo.get('picture', '')
        #     updated = True
        if updated:
            user.save(update_fields=['google_id'])  # add others if needed

    return user, created


def generate_jwt_for_user(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }