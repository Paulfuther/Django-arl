from django.urls import path

from arl.dsign.views import (
    CreateEnvelopeView,
    docusign_webhook,
    retrieve_docusign_envelope,
    list_docusign_envelope,
)

urlpatterns = [
    path("docsign/", CreateEnvelopeView.as_view(), name="Create Envelope"),
    path("docusign-webhook/", docusign_webhook, name="webhook"),
    path("docusign-envelope/", retrieve_docusign_envelope,
         name="docusign_envlope"),
    path("list-docusign-envelope-changes/", list_docusign_envelope,
         name="list_docusign_envlope-changes"),
]
