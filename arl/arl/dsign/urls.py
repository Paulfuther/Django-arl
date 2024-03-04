from django.urls import path

from arl.dsign.views import (
    CreateEnvelopeView,
    docusign_webhook,
    retrieve_docusign_envelope,
    list_docusign_envelope,
    get_docusign_template,
)

urlpatterns = [
    path("docsign/", CreateEnvelopeView.as_view(), name="CreateEnvelope"),
    path("docusign-webhook/", docusign_webhook, name="webhook"),
    path("docusign-envelope/", retrieve_docusign_envelope,
         name="docusign_envlope"),
    path("list-docusign-envelope-changes/", list_docusign_envelope,
         name="list_docusign_envlope-changes"),
    path("list_templates/", get_docusign_template, name='doc_template')
]
