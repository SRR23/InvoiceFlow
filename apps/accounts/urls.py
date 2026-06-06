from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView,
    LoginView,
    LogoutView,
    UserProfileView,
    GoogleLoginAPIView,
    PasswordResetRequestView,
    PasswordResetVerifyView,
    PasswordResetConfirmView,
)

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("google/", GoogleLoginAPIView.as_view(), name="google_login"),
    path("profile/", UserProfileView.as_view(), name="profile"),
    path(
        "password-reset/request/",
        PasswordResetRequestView.as_view(),
        name="password_reset_request",
    ),
    path(
        "password-reset/verify/",
        PasswordResetVerifyView.as_view(),
        name="password_reset_verify",
    ),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
]