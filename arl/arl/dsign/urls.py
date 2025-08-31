from django.urls import path

from arl.dsign.views import (
    CreateEnvelopeView,
    bulk_upload_signed_documents_view,
    create_new_document_page,
    docusign_close,
    docusign_webhook,
    edit_document_page,
    get_docusign_template,
    in_app_signing_dashboard,
    list_docusign_envelope,
    retrieve_docusign_envelope,
    set_new_hire_template,
    start_in_app_signing,
    waiting_for_others_view,
    upload_employee_documents,
    upload_site_documents
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
    # path("templates/edit/<str:template_id>/", edit_template, name="edit_template"),
    path("docusign-close/", docusign_close, name="docusign_close"),
    path(
        "docusign/new-document/",
        create_new_document_page,
        name="create_new_document_page",
    ),
    path(
        "docusign/edit-document/<str:template_id>/",
        edit_document_page,
        name="edit_document_page",
    ),
    path(
        "set-new-hire-template/<int:template_id>/",
        set_new_hire_template,
        name="set_new_hire_template",
    ),
    path(
        "bulk-upload-documents/",
        bulk_upload_signed_documents_view,
        name="bulk_upload_signed_documents",
    ),
    path("in-app-signing/", in_app_signing_dashboard, name="in_app_signing_dashboard"),
    path(
        "start-in-app-signing/<int:template_id>/",
        start_in_app_signing,
        name="start_in_app_signing",
    ),
    path(
        "hr/upload-employee-doc/",
        upload_employee_documents,
        name="upload_employee_documents",
    ),
    path("hr/documents/upload/site/", upload_site_documents, name="upload_site_documents"),
    
]
