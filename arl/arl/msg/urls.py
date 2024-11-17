from django.urls import path

from arl.msg.views import (EmailEventList, FetchTwilioCallsView,
                           FetchTwilioView, SendEmailView, SendSMSView,
                           SendTemplateEmailView, SendTemplateWhatsAppView,
                           click_thank_you, comms, sendgrid_webhook,
                           sms_success_view, template_email_success_view,
                           template_whats_app_success_view, whatsapp_webhook,
                           carwash_targets, message_summary_view, TwilioView,
                           sendgrid_webhook_view, email_event_summary_view,
                           campaign_setup_view)

urlpatterns = [
    path("send-sms/", SendSMSView.as_view(), name="send_sms_view"),
    path("send-email/", SendEmailView.as_view(), name="send_email_view"),
    path(
        "send-template-email/",
        SendTemplateEmailView.as_view(),
        name="send_template_email_view",
    ),
    path("send-one-off-sms/", SendSMSView.as_view(), name="send_one_off_sms_view"),
    path("sendgrid_hook/", sendgrid_webhook, name="sendgrid_webhook"),
    path("sms-success/", sms_success_view, name="sms_success"),
    path(
        "send-whatsapp/",
        SendTemplateWhatsAppView.as_view(),
        name="send_whats_app_template_view",
    ),
    path(
        "template-email-success/",
        template_email_success_view,
        name="template_email_success",
    ),
    path(
        "template-whats_app-success/",
        template_whats_app_success_view,
        name="template_whats_app_success",
    ),
    path("fetch-twilio/", FetchTwilioView.as_view(), name="fetch_twilio"),
    path(
        "fetch-twilio-calls/", FetchTwilioCallsView.as_view(), name="fetch_twilio_calls"
    ),
    path("api/data/", EmailEventList, name="data-list"),
    path("thank-you/", click_thank_you, name="thank_you"),
    path("comms/", comms, name="comms"),
    path('webhook/whatsapp/', whatsapp_webhook, name='whatsapp_webhook'),
    path('carwash/targets/', carwash_targets, name='carwash_targets'),
    # path('message-summary/', message_summary_view, name='message_summary'),
    # Route for listing messages
    path('messages/', TwilioView.as_view(), name='list_messages'),

    # Route for summarizing costs
    path('message-summary/', TwilioView.as_view(), name='summarize_costs'),
    path('sendgrid-webhook/', sendgrid_webhook_view, name='sendgrid_webhook_view'),
    path('email-event-summary/', email_event_summary_view, name='email_event_summary'),
    path("campaign/setup/", campaign_setup_view, name="campaign_setup"),
]
