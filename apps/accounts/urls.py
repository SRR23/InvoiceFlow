from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView,
    LoginView,
    GoogleOAuthURLView,
    GoogleOAuthCallbackView,
    LogoutView,
    UserProfileView,
)

app_name = 'accounts'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('google/', GoogleOAuthURLView.as_view(), name='google-oauth-url'),
    path('google/callback/', GoogleOAuthCallbackView.as_view(), name='google-oauth-callback'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('profile/', UserProfileView.as_view(), name='profile'),
]
