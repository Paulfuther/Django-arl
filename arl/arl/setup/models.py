from django.db import models
from arl.user.models import Employer
import logging
from cryptography.fernet import Fernet
from django.conf import settings


logger = logging.getLogger(__name__)


cipher = Fernet(settings.SECRET_ENCRYPTION_KEY)


class TenantApiKeys(models.Model):
    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name="api_keys")

    # Twilio Credentials
    account_sid = models.CharField(max_length=100, blank=True, null=True)  # Twilio SID
    auth_token = models.CharField(max_length=100, blank=True, null=True)  # Twilio Auth Token
    phone_number = models.CharField(max_length=20, blank=True, null=True)  # Twilio Phone
    phone_number_sid = models.CharField(max_length=100, blank=True, null=True)
    messaging_service_sid = models.CharField(max_length=100, blank=True, null=True)  # ✅ Twilio Messaging Service ID
    notify_service_sid = models.CharField(max_length=100, blank=True, null=True)

    # SendGrid Credentials
    sender_email = models.EmailField(blank=True, null=True)  # SendGrid Sender Email
    verified_sender_email = models.EmailField(blank=True, null=True)  # ✅ SendGrid Verified Email

    # Status Tracking
    status = models.CharField(max_length=50, choices=[("Active", "Active"), ("Error", "Error")], default="Active")
    is_active = models.BooleanField(default=True)  # Easier filtering

    # Timestamp Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # Tracks updates

    def set_auth_token(self, raw_token):
        """Encrypt and store the Twilio Auth Token securely."""
        self._auth_token = cipher.encrypt(raw_token.encode())

    def get_auth_token(self):
        """Decrypt and return the Twilio Auth Token."""
        return cipher.decrypt(self._auth_token).decode() if self._auth_token else None

    def __str__(self):
        return f"API Keys for {self.employer.name}"
