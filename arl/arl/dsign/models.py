from django.db import models
from arl.user.models import CustomUser


class DocuSignTemplate(models.Model):
    template_id = models.CharField(max_length=100, unique=True)
    template_name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.template_name}"
    

class ProcessedDocsignDocument(models.Model):
    envelope_id = models.CharField(max_length=255, unique=True)
    processed_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='processed_documents')

    def __str__(self):
        return f"{self.envelope_id} - {self.user.username}"
