from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.timezone import now

from arl.user.models import CustomUser, Employer


class Twimlmessages(models.Model):
    twimlname = models.CharField(max_length=100)
    twimlid = models.CharField(max_length=100)

    def __str__(self):
        return "%r" % (self.twimlname)


class BulkEmailSendgrid(models.Model):
    templatename = models.CharField(max_length=100)
    templateid = models.CharField(max_length=100)

    def __str__(self):
        return "%r" % (self.templatename)


class EmailEvent(models.Model):
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, null=True, blank=True
    )
    username = models.CharField(max_length=150, default="unknown")
    email = models.EmailField()
    event = models.CharField(max_length=10)
    ip = models.GenericIPAddressField()
    sg_event_id = models.CharField(max_length=255)
    sg_message_id = models.CharField(max_length=255)
    sg_template_id = models.CharField(max_length=255)
    sg_template_name = models.CharField(max_length=255)
    timestamp = models.DateTimeField()
    url = models.URLField()
    useragent = models.TextField()

    def __str__(self):
        return f"{self.email} - {self.event}"

    class Meta:
        ordering = ["-timestamp"]


class SmsLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    level = models.CharField(max_length=10)
    message = models.TextField()

    def __str__(self):
        return f"{self.timestamp} - {self.level}: {self.message}"


class EmailLog(models.Model):
    employer = models.ForeignKey("user.Employer", on_delete=models.CASCADE, related_name="email_logs")
    sender_email = models.EmailField(help_text="The verified sender email used")
    template_id = models.CharField(
        max_length=100, help_text="SendGrid Template ID used"
    )
    template_name = models.CharField(max_length=255, blank=True, null=True)
    sent_at = models.DateTimeField(default=now)
    status = models.CharField(
        max_length=20,
        choices=[("SUCCESS", "Success"), ("FAILED", "Failed")],
        default="SUCCESS",
    )
    error_message = models.TextField(blank=True, null=True, help_text="Error details if failed")

    def __str__(self):
        return f"EmailLog {self.id} - {self.employer.name} - {self.sent_at.strftime('%Y-%m-%d %H:%M')}"


class EmailTemplate(models.Model):
    employers = models.ManyToManyField(
        Employer,
        blank=True,
        related_name="email_templates"
    )
    name = models.CharField(
        max_length=100,
        null=True,
        help_text="The name of the email template (e.g., 'New Hire Onboarding')"
    )  # ✅ Allow same name for multiple employers
    sendgrid_id = models.TextField()  # ✅ Store SendGrid Template ID
    include_in_report = models.BooleanField(default=False)  # ✅ For analytics

    def __str__(self):
        return f"{self.name} - {', '.join([emp.name for emp in self.employers.all()])}"


class WhatsAppTemplate(models.Model):
    name = models.CharField(
        max_length=255, help_text="Friendly name of the WhatsApp template"
    )
    content_sid = models.CharField(
        max_length=255,
        unique=True,
        help_text="The unique identifier for the template (e.g., Twilio Content SID)",
    )
    description = models.TextField(
        blank=True, help_text="Description of what this template is used for"
    )

    def __str__(self):
        return f"{self.name} - {self.content_sid}"

    class Meta:
        verbose_name = "WhatsApp Template"
        verbose_name_plural = "WhatsApp Templates"


class UserConsent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="consents"
    )
    consent_type = models.CharField(
        max_length=100, help_text="Type of consent, e.g., 'SMS', 'Email'"
    )
    is_granted = models.BooleanField(
        default=False, help_text="Whether the user has granted consent"
    )
    granted_on = models.DateTimeField(
        null=True, blank=True, help_text="When the consent was granted"
    )
    revoked_on = models.DateTimeField(
        null=True, blank=True, help_text="When the consent was revoked, if applicable"
    )

    def __str__(self):
        status = "Granted" if self.is_granted else "Revoked"
        return f"{self.user.username} - {self.consent_type} - {status}"

    class Meta:
        unique_together = (
            "user",
            "consent_type",
        )  # Ensures uniqueness for the combination of user and consent type


class Message(models.Model):
    sender = models.CharField(max_length=20)
    receiver = models.CharField(max_length=20)
    message_status = models.CharField(max_length=20)
    username = models.CharField(max_length=100, blank=True, null=True)
    action_time = models.DateTimeField(default=timezone.now)
    template_used = models.BooleanField(default=False)
    message_type = models.CharField(max_length=10, default='WhatsApp')  # 'WhatsApp' or 'SMS'

    def __str__(self):
        return f"{self.message_type} message from {self.sender} to {self.receiver}, status {self.message_status}, at {self.action_time}"


class EmailList(models.Model):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)



