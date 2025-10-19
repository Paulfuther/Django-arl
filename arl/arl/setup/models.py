from django.db import models
from arl.user.models import Employer
import logging
from cryptography.fernet import Fernet
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django_countries.fields import CountryField
from phonenumber_field.modelfields import PhoneNumberField


logger = logging.getLogger(__name__)


cipher = Fernet(settings.SECRET_ENCRYPTION_KEY)
# print(cipher, "Secret Key :", settings.SECRET_ENCRYPTION_KEY)


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


class StripePlan(models.Model):
    name = models.CharField(max_length=100)  # e.g., "Standard Plan"
    stripe_price_id = models.CharField(max_length=100)  # e.g., "price_300_default"
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "user_stripeplan"

    def __str__(self):
        return f"{self.name} - ${self.amount}"


class EmployerRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    company_name = models.CharField(max_length=255)
    senior_contact_first_name = models.CharField(max_length=100)
    senior_contact_last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True, help_text="Contact email for the employer")
    address = models.CharField(max_length=100, null=True, blank=True)
    address_two = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state_province = models.CharField(max_length=100, null=True, blank=True)
    country = CountryField(null=True, blank=True)
    phone_number = PhoneNumberField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True, null=True)
    updated = models.DateTimeField(auto_now=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")

    verified_sender_local = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        help_text="Enter only the part before '@yourdomain.com'"
    )
    verified_sender_email = models.EmailField(
        max_length=255,
        unique=True,
        blank=True,
        null=True,
        help_text="This is the full email generated based on your input."
    )
    stripe_plan = models.ForeignKey(
        StripePlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Select the Stripe plan for this employer (defaults to Free Plan)"
    )

    def clean(self):
        User = get_user_model()
        if User.objects.filter(email__iexact=self.email).exists():
            raise ValidationError("A user with this email already exists.")

    def save(self, *args, **kwargs):
        if not self.stripe_plan:
            try:
                self.stripe_plan = StripePlan.objects.get(stripe_price_id="price_000_free")
            except StripePlan.DoesNotExist:
                pass  # or raise an error

        if self.verified_sender_local:
            self.verified_sender_email = f"{self.verified_sender_local}@1553690ontarioinc.com"
        else:
            self.verified_sender_email = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.company_name} ({self.get_status_display()})"

    class Meta:
        db_table = "user_employerrequest"


class StripePayment(models.Model):
    employer = models.OneToOneField("user.Employer", on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("300.00"))
    is_paid = models.BooleanField(default=False)
    payment_date = models.DateTimeField(null=True, blank=True)

    # Stripe-related fields
    stripe_session_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def mark_paid(self, session_id=None, subscription_id=None, customer_id=None):
        self.is_paid = True
        self.payment_date = timezone.now()
        if session_id:
            self.stripe_session_id = session_id
        if subscription_id:
            self.stripe_subscription_id = subscription_id
        if customer_id:
            self.stripe_customer_id = customer_id
        self.save()

    def __str__(self):
        return f"Payment for {self.employer.name} - {'PAID' if self.is_paid else 'UNPAID'}"

    class Meta:
        db_table = "user_stripepayment"

