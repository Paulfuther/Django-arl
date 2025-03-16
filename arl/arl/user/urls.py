from django.contrib.auth import views as auth_views
from django.urls import path

from .views import (CheckPhoneNumberUniqueView, RegisterView,
                    TaskResultListView, admin_verification_page,
                    check_verification, fetch_managers, home_view, login_view,
                    logout_view, request_verification, verification_page,
                    verify_twilio_phone_number, phone_format,
                    EmployerRegistrationView, landing_page,
                    hr_invite_new_hire, approve_employer,
                    reject_employer, close_twilio_sub)
from django.views.generic import TemplateView


urlpatterns = [
    path("login", login_view, name="login"),
    path("register/<str:token>/", RegisterView.as_view(), name="register"),
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
    path("fetch_managers/", fetch_managers, name="fetch_managers"),
    path('task-results/', TaskResultListView.as_view(), name='task_results'),
    path('verify-phone/<str:phone_number>/', verify_twilio_phone_number, name='verify_twilio_phone'),
    path('phone-format/', phone_format, name='phone_format'),
    path("register-employer/", EmployerRegistrationView.as_view(), name="register_employer"),
    path("registration-success/",
         TemplateView.as_view(template_name="user/employer_success.html"),
         name="employer_registration_success"),
    path("", landing_page, name="landing"),
    path("hr/invite/", hr_invite_new_hire, name="hr_invite"),
    path("approve-employer/<int:pk>/", approve_employer, name="approve_employer"),
    path("close-twilio-sub/<str:subaccount_sid>", close_twilio_sub, name = "close_twilio_sub"),
   
    
]
