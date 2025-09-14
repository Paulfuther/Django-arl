import uuid
from django.db import models
from django.conf import settings


class StoreDocumentJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    sdf_id = models.IntegerField()              # link to SignedDocumentFile.id
    tmp_path = models.CharField(max_length=1024)
    original_name = models.CharField(max_length=255)
    original_ct = models.CharField(max_length=100, blank=True, default="")
    status = models.CharField(max_length=16, default="queued")  # queued|processing|done|error
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


