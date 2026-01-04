from django.urls import path

from arl.dsign.views import (
    CreateEnvelopeView,
    bulk_upload_signed_documents_view,
    company_doc_notes_cancel,
    company_doc_notes_cancel_mobile,
    company_doc_notes_edit,
    company_doc_notes_edit_mobile,
    company_doc_notes_save,
    company_doc_notes_save_mobile,
    company_docs_search,
    create_new_document_page,
    documents_dashboard,
    docusign_close,
    docusign_webhook,
    edit_document_page,
    employee_docs_panel,
    employee_docs_search,
    get_docusign_template,
    in_app_signing_dashboard,
    list_docusign_envelope,
    retrieve_docusign_envelope,
    set_new_hire_template,
    start_in_app_signing,
    upload_company_documents_async,
    upload_employee_documents,
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
    path("documents/", documents_dashboard, name="documents_dashboard"),
    path(
        "documents/search/employee/", employee_docs_search, name="employee_docs_search"
    ),
    path("documents/search/company/", company_docs_search, name="company_docs_search"),
    path(
        "documents/company/upload/",
        upload_company_documents_async,
        name="upload_company_documents_async",
    ),
    path(
        "documents/employee/<int:user_id>/panel/",
        employee_docs_panel,
        name="employee_docs_panel",
    ),
    path(
        "docs/company/<int:doc_id>/notes/edit/",
        company_doc_notes_edit,
        name="company_doc_notes_edit",
    ),
    path(
        "docs/company/<int:doc_id>/notes/save/",
        company_doc_notes_save,
        name="company_doc_notes_save",
    ),
    path(
        "docs/company/<int:doc_id>/notes/mobile/edit/",
        company_doc_notes_edit_mobile,
        name="company_doc_notes_edit_mobile",
    ),
    path(
        "docs/company/<int:doc_id>/notes/mobile/save/",
        company_doc_notes_save_mobile,
        name="company_doc_notes_save_mobile",
    ),
    path(
        "docs/company/<int:doc_id>/notes/mobile/cancel/",
        company_doc_notes_cancel_mobile,
        name="company_doc_notes_cancel_mobile",
    ),
    path(
        "docs/company/<int:doc_id>/notes/cancel/",
        company_doc_notes_cancel,
        name="company_doc_notes_cancel",
    ),
]
