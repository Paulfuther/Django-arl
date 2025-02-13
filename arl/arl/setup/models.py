from django.db import models
from django.contrib.auth import get_user_model


class TenantAPIKeys(models.Model):
    employer = models.OneToOneField("user.Employer", on_delete=models.CASCADE, related_name="api_keys")

    # Twilio
    twilio_account_sid = models.CharField(max_length=100, blank=True, null=True)
    twilio_auth_token = models.CharField(max_length=100, blank=True, null=True)
    twilio_service_sid = models.CharField(max_length=100, blank=True, null=True)

    # SendGrid
    sendgrid_api_key = models.CharField(max_length=255, blank=True, null=True)

    # Dropbox
    dropbox_access_token = models.CharField(max_length=255, blank=True, null=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"API Keys for {self.employer.name}"
