from django.urls import path

from arl.dsign.views import (
    CreateEnvelopeView,
    docusign_webhook,
    get_docusign_template,
    list_docusign_envelope,
    retrieve_docusign_envelope,
    waiting_for_others_view,
    edit_document_page, docusign_close,
    create_new_document_page,
    set_new_hire_template,
    bulk_upload_signed_documents_view,
    in_app_signing_dashboard,
    start_in_app_signing
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
    #path("templates/edit/<str:template_id>/", edit_template, name="edit_template"),
    path("docusign-close/", docusign_close, name="docusign_close"),
    path("docusign/new-document/", create_new_document_page, name="create_new_document_page"),
    path("docusign/edit-document/<str:template_id>/", edit_document_page, name="edit_document_page"),
    path("set-new-hire-template/<int:template_id>/", set_new_hire_template, name="set_new_hire_template"),
    path("bulk-upload-documents/", bulk_upload_signed_documents_view, name="bulk_upload_signed_documents"),
    path('in-app-signing/', in_app_signing_dashboard, name='in_app_signing_dashboard'),
    path('start-in-app-signing/<int:template_id>/', start_in_app_signing, name='start_in_app_signing'),
]
