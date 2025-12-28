from django.db import models

from arl.user.models import CustomUser, Employer, Store


class DocuSignTemplate(models.Model):
    id = models.AutoField(primary_key=True)
    employer = models.ForeignKey(
        "user.Employer",
        on_delete=models.CASCADE,
        related_name="docusign_templates",
        help_text="Employer associated with this template",
    )
    template_id = models.CharField(max_length=100)
    template_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    is_new_hire_template = models.BooleanField(default=False)
    is_ready_to_send = models.BooleanField(default=False)
    is_in_app_signing_template = models.BooleanField(default=False)
    is_company_document = models.BooleanField(default=False)

    class Meta:
        unique_together = ("employer", "template_id")  # Ensure uniqueness per employer

    def __str__(self):
        return f"{self.template_name} (Employer: {self.employer})"


class ProcessedDocsignDocument(models.Model):
    envelope_id = models.CharField(max_length=255)
    template_name = models.CharField(
        max_length=255, blank=True, null=True
    )  # Added field
    processed_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,  # ✅ Changed from CASCADE to SET_NULL
        null=True,  # ✅ Allow NULL in database
        blank=True,  # ✅ Allow form/model level blank
        related_name="processed_documents",
    )
    employer = models.ForeignKey(
        "user.Employer", on_delete=models.CASCADE, related_name="processed_documents"
    )
    is_company_document = models.BooleanField(default=False)

    def __str__(self):
        envelope = self.envelope_id or "No Envelope ID"
        user = self.user.username if self.user else "No User"
        template = self.template_name or "No Template"
        return f"{envelope} - {user} - {template}"


class SignedDocumentFile(models.Model):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="signed_documents",
    )
    employer = models.ForeignKey(Employer, on_delete=models.CASCADE)

    # NEW: link docs to a store (site)
    store = models.ForeignKey(
        Store, on_delete=models.CASCADE, null=True, blank=True, related_name="documents"
    )

    envelope_id = models.CharField(max_length=255)
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=512)
    template_name = models.CharField(max_length=255, null=True, blank=True)
    document_title = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # Keep using this flag to distinguish non-employee docs (company/store)
    is_company_document = models.BooleanField(default=False)

    def clean(self):
        # Ensure either user OR store is set (but not both / not neither)
        if bool(self.user) == bool(self.store):
            raise ValidationError(
                "Document must be linked to either a user or a store."
            )
