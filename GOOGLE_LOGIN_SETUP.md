# Google Login Setup Guide

This document provides comprehensive instructions for setting up Google OAuth authentication in the InvoiceFlow project.

## Overview

InvoiceFlow uses **Google ID Token (JWT) verification** for secure Google OAuth authentication. The implementation:

- ✅ Uses Google's official `google-auth` library for token verification
- ✅ Accepts Google ID tokens (JWT) from frontend
- ✅ Automatically creates or logs in users
- ✅ Returns JWT access and refresh tokens for API authentication
- ✅ Links Google accounts to existing users by email
- ✅ Sets `is_business_user=True` for all Google-authenticated users

## Architecture

```
Frontend (React/SPA)
    ↓
Google Sign-In SDK → Get ID Token (JWT)
    ↓
POST /api/auth/google/ { "id_token": "..." }
    ↓
Backend verifies token with Google
    ↓
Create/Get User → Generate JWT tokens
    ↓
Return { user, access, refresh }
```

## Prerequisites

1. **Google Cloud Console Account**
2. **OAuth 2.0 Client ID** from Google Cloud Console
3. **Python dependencies** installed (`google-auth`, `google-auth-oauthlib`)

## Step 1: Google Cloud Console Setup

### 1.1 Create or Select a Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your project ID

### 1.2 Configure OAuth Consent Screen

1. Navigate to **APIs & Services** → **OAuth consent screen**
2. Choose **External** (for public users) or **Internal** (for G Suite)
3. Fill in required information:
   - **App name**: InvoiceFlow
   - **User support email**: Your email
   - **Developer contact information**: Your email
4. Add scopes:
   - `email`
   - `profile`
   - `openid`
5. Add test users (if in Testing mode)
6. Save and continue

### 1.3 Create OAuth 2.0 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth 2.0 Client ID**
3. Choose **Web application** as application type
4. Configure:
   - **Name**: InvoiceFlow Web Client
   - **Authorized JavaScript origins**:
     - `http://localhost:3000` (development)
     - `https://yourdomain.com` (production)
   - **Authorized redirect URIs** (optional for ID token flow):
     - `http://localhost:3000/auth/google/callback` (development)
     - `https://yourdomain.com/auth/google/callback` (production)
5. Click **Create**
6. **Copy the Client ID** - you'll need this for environment variables

> **Note**: For ID token flow, redirect URIs are optional since the frontend handles the OAuth flow and sends the token directly to the backend.

## Step 2: Backend Configuration

### 2.1 Environment Variables

Add the following to your `.env` file:

```bash
# Google OAuth Configuration
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret  # Optional for ID token flow
```

**Important Notes:**
- `GOOGLE_CLIENT_ID` is **required** - used to verify ID tokens
- `GOOGLE_CLIENT_SECRET` is **optional** for ID token flow (only needed for server-side OAuth flows)

### 2.2 Verify Settings

The settings are configured in `config/settings/base.py`:

```python
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
```

### 2.3 Dependencies

Ensure these packages are installed (already in `requirements/base.txt`):

```txt
google-auth>=2.23.0
google-auth-oauthlib>=1.1.0
```

Install dependencies:

```bash
pip install -r requirements/base.txt
```

## Step 3: Database Setup

### 3.1 User Model

The `User` model already includes Google OAuth support:

- `google_id`: Stores Google user ID (sub claim from ID token)
- `email`: Used to link existing users with Google accounts
- `is_business_user`: Automatically set to `True` for Google-authenticated users

### 3.2 Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

## Step 4: API Endpoint

### 4.1 Endpoint Details

**URL**: `POST /api/auth/google/`

**Request Body**:
```json
{
  "id_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6IjEyMzQ1Njc4OTAiLCJ0eXAiOiJKV1QifQ..."
}
```

**Success Response (200)**:
```json
{
  "user": {
    "id": 42,
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "is_business_user": true,
    "google_id": "123456789012345678901"
  },
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Error Responses**:

- **400 Bad Request**: Invalid or missing ID token
  ```json
  {
    "detail": "id_token is required"
  }
  ```

- **400 Bad Request**: Token verification failed
  ```json
  {
    "detail": "Invalid Google ID token: Token expired"
  }
  ```

- **500 Internal Server Error**: Server error during authentication

### 4.2 Authentication Flow

1. Frontend obtains ID token from Google Sign-In SDK
2. Frontend sends `POST /api/auth/google/` with `id_token` in body
3. Backend verifies token with Google's servers
4. Backend creates or retrieves user:
   - If user exists with same email → logs in
   - If user exists with same `google_id` → logs in
   - Otherwise → creates new user
5. Backend generates JWT tokens
6. Backend returns user data and tokens

## Step 5: Frontend Integration

### 5.1 React Example (using `@react-oauth/google`)

```bash
npm install @react-oauth/google
```

```tsx
import { GoogleOAuthProvider, useGoogleLogin } from '@react-oauth/google';

function LoginButton() {
  const login = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
      // Get ID token from credential response
      const credentialResponse = await fetch(
        `https://oauth2.googleapis.com/tokeninfo?id_token=${tokenResponse.access_token}`
      );
      const credential = await credentialResponse.json();
      
      // Send to backend
      const response = await fetch('http://localhost:8000/api/auth/google/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          id_token: credential.id_token || tokenResponse.access_token,
        }),
      });
      
      const data = await response.json();
      
      // Store tokens
      localStorage.setItem('access_token', data.access);
      localStorage.setItem('refresh_token', data.refresh);
      
      // Redirect or update UI
      console.log('Logged in:', data.user);
    },
    onError: () => {
      console.error('Login failed');
    },
  });

  return <button onClick={() => login()}>Sign in with Google</button>;
}

function App() {
  return (
    <GoogleOAuthProvider clientId="YOUR_GOOGLE_CLIENT_ID">
      <LoginButton />
    </GoogleOAuthProvider>
  );
}
```

### 5.2 Using Google Identity Services (Recommended)

```html
<!DOCTYPE html>
<html>
<head>
  <script src="https://accounts.google.com/gsi/client" async defer></script>
</head>
<body>
  <div id="g_id_onload"
       data-client_id="YOUR_GOOGLE_CLIENT_ID"
       data-callback="handleCredentialResponse">
  </div>
  <div class="g_id_signin" data-type="standard"></div>

  <script>
    function handleCredentialResponse(response) {
      // response.credential is the ID token (JWT)
      fetch('http://localhost:8000/api/auth/google/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          id_token: response.credential,
        }),
      })
      .then(res => res.json())
      .then(data => {
        // Store tokens
        localStorage.setItem('access_token', data.access);
        localStorage.setItem('refresh_token', data.refresh);
        console.log('Logged in:', data.user);
      })
      .catch(err => console.error('Login failed:', err));
    }
  </script>
</body>
</html>
```

### 5.3 Using JWT Tokens

After successful login, use the JWT tokens for authenticated requests:

```javascript
// Include access token in Authorization header
fetch('http://localhost:8000/api/invoices/', {
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
    'Content-Type': 'application/json',
  },
});

// Refresh token when access token expires
async function refreshAccessToken() {
  const response = await fetch('http://localhost:8000/api/auth/token/refresh/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      refresh: localStorage.getItem('refresh_token'),
    }),
  });
  
  const data = await response.json();
  localStorage.setItem('access_token', data.access);
  return data.access;
}
```

## Step 6: Testing

### 6.1 Test the Endpoint

```bash
# Using curl
curl -X POST http://localhost:8000/api/auth/google/ \
  -H "Content-Type: application/json" \
  -d '{
    "id_token": "YOUR_GOOGLE_ID_TOKEN_HERE"
  }'
```

### 6.2 Get a Test ID Token

1. Use Google's [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/)
2. Or use the frontend integration to get a real ID token
3. Decode the token at [jwt.io](https://jwt.io/) to verify claims

### 6.3 Verify Token Claims

A valid Google ID token should contain:

```json
{
  "iss": "https://accounts.google.com",
  "sub": "123456789012345678901",
  "email": "user@example.com",
  "email_verified": true,
  "name": "John Doe",
  "given_name": "John",
  "family_name": "Doe",
  "picture": "https://lh3.googleusercontent.com/...",
  "aud": "your-client-id.apps.googleusercontent.com",
  "iat": 1234567890,
  "exp": 1234571490
}
```

## Security Considerations

### ✅ Implemented Security Features

1. **Token Verification**: Uses Google's official library to verify token signature and claims
2. **Issuer Validation**: Checks that token is from `accounts.google.com`
3. **Email Verification**: Requires `email_verified=true`
4. **Audience Validation**: Verifies token is for your `GOOGLE_CLIENT_ID`
5. **JWT Tokens**: Uses short-lived access tokens and refresh tokens
6. **HTTPS**: Always use HTTPS in production

### ⚠️ Best Practices

1. **Never expose Client Secret** in frontend code
2. **Use HTTPS** in production
3. **Validate tokens server-side** (already implemented)
4. **Store tokens securely** (use httpOnly cookies or secure storage)
5. **Implement token refresh** logic in frontend
6. **Set appropriate token expiration** times
7. **Monitor for suspicious activity**

## Troubleshooting

### Error: "Invalid Google ID token"

**Possible causes:**
- Token expired (check `exp` claim)
- Wrong `GOOGLE_CLIENT_ID` in settings
- Token not from Google (check `iss` claim)
- Token tampered with (signature verification failed)

**Solution:**
- Verify `GOOGLE_CLIENT_ID` matches your Google Cloud Console client ID
- Check token expiration time
- Ensure token is fresh (obtained recently)

### Error: "Email not verified by Google"

**Cause:** User's Google account email is not verified

**Solution:** User must verify their email in Google account settings

### Error: "id_token is required"

**Cause:** Request body missing `id_token` field

**Solution:** Ensure frontend sends `{"id_token": "..."}` in request body

### User Not Created

**Possible causes:**
- Email already exists with different `google_id`
- Database constraint violation

**Solution:**
- Check existing users in database
- Verify `google_id` field is unique
- Check logs for detailed error messages

## Code Structure

### Key Files

- **API Endpoint**: `apps/accounts/views.py` → `GoogleLoginAPIView`
- **Service Functions**: `apps/accounts/services/google_auth.py`
  - `verify_google_id_token()`: Verifies ID token with Google
  - `get_or_create_google_user()`: Creates or retrieves user
  - `generate_jwt_for_user()`: Generates JWT tokens
- **User Model**: `apps/accounts/models.py` → `User` model with `google_id` field
- **URL Configuration**: `apps/accounts/urls.py` → `/api/auth/google/`
- **Settings**: `config/settings/base.py` → `GOOGLE_CLIENT_ID`

### Service Functions

```python
# apps/accounts/services/google_auth.py

def verify_google_id_token(token: str) -> dict:
    """Verify Google ID token and return claims."""
    # Uses google.oauth2.id_token.verify_oauth2_token()
    # Validates issuer, email_verified, and audience

def get_or_create_google_user(idinfo: dict) -> tuple[User, bool]:
    """Get or create user from Google ID token claims."""
    # Creates user if email doesn't exist
    # Links to existing user if email matches
    # Updates google_id if changed

def generate_jwt_for_user(user: User) -> dict:
    """Generate JWT access and refresh tokens."""
    # Uses rest_framework_simplejwt.tokens.RefreshToken
```

## Production Deployment

### Environment Variables

Set in your production environment:

```bash
GOOGLE_CLIENT_ID=your-production-client-id.apps.googleusercontent.com
```

### Google Cloud Console

1. Create separate OAuth client for production
2. Add production domain to authorized origins
3. Update OAuth consent screen for production
4. Test with production domain

### Monitoring

- Monitor authentication logs
- Track failed login attempts
- Monitor token refresh rates
- Set up alerts for authentication errors

## Additional Resources

- [Google Identity Services Documentation](https://developers.google.com/identity/gsi/web)
- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [JWT.io - Decode JWT tokens](https://jwt.io/)
- [Django REST Framework Simple JWT](https://django-rest-framework-simplejwt.readthedocs.io/)

## Support

For issues or questions:
1. Check server logs: `logs/django.log`
2. Check Django admin for user records
3. Verify Google Cloud Console configuration
4. Test with Google's OAuth 2.0 Playground

---

**Last Updated**: 2025-03-15
**Version**: 1.0
