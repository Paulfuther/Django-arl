from django.contrib.auth import views as auth_views
from django.urls import path

from .views import (CheckPhoneNumberUniqueView, RegisterView,
                    TaskResultListView, admin_verification_page,
                    check_verification, fetch_managers, home_view, login_view,
                    logout_view, request_verification, verification_page,
                    verify_twilio_phone_number, phone_format,
                    EmployerRegistrationView, landing_page,
                    approve_employer, reject_employer, close_twilio_sub,
                    hr_dashboard, cancel_invite, resend_invite,
                    hr_document_view, download_signed_document,
                    fetch_signed_docs_by_user)
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
    path("hr/dashboard/", hr_dashboard, name="hr_dashboard"),
    path("hr/invite/cancel/<int:invite_id>/", cancel_invite, name="cancel_invite"),
    path("hr/invite/resend/<int:invite_id>/", resend_invite, name="resend_invite"),
    path("hr/documents/", hr_document_view, name="hr_document_view"),
    path("hr/documents/fetch/<int:user_id>/", fetch_signed_docs_by_user, name="fetch_signed_docs_by_user"),
    path("hr/documents/download/<int:doc_id>/", download_signed_document, name="download_signed_document"),
    path("approve-employer/<int:pk>/", approve_employer, name="approve_employer"),
    path("close-twilio-sub/<str:subaccount_sid>", close_twilio_sub, name = "close_twilio_sub"),
   
    
]
