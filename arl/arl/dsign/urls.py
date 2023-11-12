from django.urls import path

from arl.dsign.views import create_envelope, docusign_webhook

urlpatterns = [
    path("docsign/", create_envelope, name="Create Envelope"),
    path("docusign-webhook/", docusign_webhook, name="webhook"),
]