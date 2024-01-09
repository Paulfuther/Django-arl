from django.urls import path

from arl.msg.views import (
    EmailEventListView,
    FetchTwilioCallsView,
    FetchTwilioView,
    SendEmailView,
    SendSMSView,
    SendTemplateEmailView,
    sendgrid_webhook,
    sms_success_view,
    template_email_success_view,
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
    path("sms-success/", sms_success_view, name="sms_success"),
    path(
        "template-email-success/",
        template_email_success_view,
        name="template_email_success",
    ),
    path("fetch-twilio/", FetchTwilioView.as_view(), name="fetch_twilio"),
    path(
        "fetch-twilio-calls/", FetchTwilioCallsView.as_view(), name="fetch_twilio_calls"
    ),
    path("api/data/", EmailEventListView.as_view(), name="data-list"),
]
