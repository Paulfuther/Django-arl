from django.contrib.auth import views as auth_views
from django.urls import path

from .views import (
    CheckPhoneNumberUniqueView,
    admin_verification_page,
    check_verification,
    home_view,
    login_view,
    logout_view,
    register,
    request_verification,
    verification_page,
)

urlpatterns = [
    path("", login_view, name="home"),
    path("register", register, name="register"),
    path(
        "check_phone_number_unique/",
        CheckPhoneNumberUniqueView.as_view(),
        name="check_phone_number_unique",
    ),
    path("request-verification/", request_verification, name="request_verification"),
    path("check-verification/", check_verification, name="check_verification"),
    path("login/", login_view, name="login"),
    path("verification/", verification_page, name="verification_page"),
    path(
        "admin_verification/", admin_verification_page, name="admin_verification_page"
    ),
    path("logout/", logout_view, name="logout"),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(template_name="user/password_reset.html"),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="user/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset-confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="user/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset-complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="user/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("home/", home_view, name="home"),
]
