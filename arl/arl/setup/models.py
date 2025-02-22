from django.db import models
from arl.user.models import Employer


class TenantApiKeys(models.Model):
    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name="api_keys")

    # Service Name (e.g., Twilio, SendGrid)
    service_name = models.CharField(max_length=50, choices=[
        ("twilio", "Twilio"),
        ("sendgrid", "SendGrid"),
    ])

    # Twilio Credentials
    account_sid = models.CharField(max_length=100, blank=True, null=True)  # Twilio SID
    auth_token = models.CharField(max_length=100, blank=True, null=True)  # Twilio Auth Token
    phone_number = models.CharField(max_length=20, blank=True, null=True)  # Twilio Phone
    messaging_service_sid = models.CharField(max_length=100, blank=True, null=True)  # ✅ Twilio Messaging Service ID

    # SendGrid Credentials
    sender_email = models.EmailField(blank=True, null=True)  # SendGrid Sender Email
    verified_sender_email = models.EmailField(blank=True, null=True)  # ✅ SendGrid Verified Email

    # Status Tracking
    status = models.CharField(max_length=50, choices=[("Active", "Active"), ("Error", "Error")], default="Active")
    is_active = models.BooleanField(default=True)  # Easier filtering

    # Timestamp Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # Tracks updates

    def __str__(self):
        return f"{self.employer.name} - {self.service_name}"
