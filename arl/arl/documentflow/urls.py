from django.urls import path
from .views import document_audit_log_partial

urlpatterns = [
    path("audit-log/partial/", document_audit_log_partial, name="document_audit_log_partial"),
]