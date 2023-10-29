from django.contrib.auth import views as auth_views
from django.urls import path

from arl.dbox.views import (
    delete_file,
    download_file,
    list_files,
    list_folder_contents,
    list_folders,
    upload_file,
    use_dropbox,
    view_folder,
)
from arl.dsign.views import create_envelope, docusign_webhook
from arl.incident.views import IncidentCreateView, generate_pdf, incident_form_pdf, process_incident_images

from arl.msg.views import SendSMSView, sendgrid_webhook, sms_success_view, SendTemplateEmailView, SendEmailView, send_weekly_tobacco_emails, send_weekly_tobacco_text

from .views import (
    CheckPhoneNumberUniqueView,
    admin_verification_page,
    check_verification,
    home_view,
    login_view,
    logout_view,
    register,
    request_verification,
    sms_form,
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
    path("sms_form/", sms_form, name="sms_form"),
    path("docsign/", create_envelope, name="Create Envelope"),
    path("login/", login_view, name="login"),
    path("verification/", verification_page, name="verification_page"),
    path("admin_verification/", admin_verification_page, name="admin_verification_page"),
    path("logout/", logout_view, name="logout"),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(template_name="user/password_reset.html"),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="user/password_reset_done.html"),
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
    path("use_dropbox/", use_dropbox, name="new token"),
    path("list_folders/", list_folders, name="list_folders"),
    path("list_files/", list_files, name="list_files"),
    path("list_files/<str:path>/", list_files, name="list_files"),
    path("view_folder/", view_folder, name="view_folder"),
    path("list_folder_contents/<path:path>/", list_folder_contents, name="list_folder_contents"),
    path("download_file/", download_file, name="download_file"),
    path("docusign-webhook/", docusign_webhook, name="webhook"),
    path("upload_file/", upload_file, name="upload_file"),
    path("delete_file/", delete_file, name="delete_file"),
    path("create-incident/", IncidentCreateView.as_view(), name="create-incident"),
    path("incident_upload/", process_incident_images, name="incident_upload"),
    path("incident-form-pdf/<int:incident_id>/", incident_form_pdf, name="incident_form_pdf"),
    path("generate-pdf/<int:incident_id>/", generate_pdf, name="generate_pdf"),
    path("send-sms/", SendSMSView.as_view(), name="send_sms_view"),
    path('sms-success/', sms_success_view, name='sms_success'),
    path("send-template-email/", SendTemplateEmailView.as_view(), name="send_template_email_view"),
    path("send-email/", SendEmailView.as_view(), name="send_email_view"),
    path("sendgrid_hook/", sendgrid_webhook, name="sendgrid_webhook"),
    path('send_tobacco_emails/', send_weekly_tobacco_emails, name='send_tobacco_emails'),
    path('send_tobacco_sms/', send_weekly_tobacco_text, name='send_weekly_tobacco_text'),
]
