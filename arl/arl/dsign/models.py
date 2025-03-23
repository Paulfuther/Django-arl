from django.db import models
from arl.user.models import CustomUser, Employer
import uuid


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
    
    class Meta:
        unique_together = ("employer", "template_id")  # Ensure uniqueness per employer

    def __str__(self):
        return f"{self.template_name} (Employer: {self.employer})"


class ProcessedDocsignDocument(models.Model):
    envelope_id = models.CharField(max_length=255)
    template_name = models.CharField(max_length=255, blank=True, null=True)  # Added field
    processed_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE,
                             related_name='processed_documents')
    employer = models.ForeignKey("user.Employer",
                                 on_delete=models.CASCADE,
                                 related_name="processed_documents")

    def __str__(self):
        return f"{self.envelope_id} - {self.user.username} - {self.template_name}"


class SignedDocumentFile(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="signed_documents")
    employer = models.ForeignKey(Employer, on_delete=models.CASCADE)
    envelope_id = models.CharField(max_length=255)
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=512)  # S3/Linode path
    template_name = models.CharField(max_length=255, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.file_name} for {self.user.get_full_name()}"