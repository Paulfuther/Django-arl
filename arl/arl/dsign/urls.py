from django.urls import path

from arl.dsign.views import (
    CreateEnvelopeView,
    docusign_webhook,
    get_docusign_template,
    list_docusign_envelope,
    retrieve_docusign_envelope,
    waiting_for_others_view,
)

urlpatterns = [
    path("docsign/", CreateEnvelopeView.as_view(), name="CreateEnvelope"),
    path("docusign-webhook/", docusign_webhook, name="webhook"),
    path("docusign-envelope/", retrieve_docusign_envelope, name="docusign_envlope"),
    path(
        "list-docusign-envelope-changes/",
        list_docusign_envelope,
        name="list_docusign_envlope-changes",
    ),
    path("list_templates/", get_docusign_template, name="doc_template"),
    path(
        "docusign/waiting-for-others/",
        waiting_for_others_view,
        name="waiting_for_others",
    ),
]
