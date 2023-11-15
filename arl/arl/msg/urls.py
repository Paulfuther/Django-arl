from django.urls import path

from arl.msg.views import (
    SendEmailView,
    SendSMSView,
    SendTemplateEmailView,
    sendgrid_webhook,
)

urlpatterns = [
    path("send-sms/", SendSMSView.as_view(), name="send_sms_view"),
    path("send-email/", SendEmailView.as_view(), name="send_email_view"),
    path(
        "send-template-email/",
        SendTemplateEmailView.as_view(),
        name="send_template_email_view",
    ),
    path("sendgrid_hook/", sendgrid_webhook, name="sendgrid_webhook"),
]