from django.db import models


# Create your models here.
class DocumentFlow(models.Model):
    employer = models.ForeignKey(
        "user.Employer",
        on_delete=models.CASCADE,
        related_name="document_flows",
    )
    name = models.CharField(max_length=255, default="New Hire Document Flow")
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.employer} - {self.name}"


class DocumentFlowStep(models.Model):
    flow = models.ForeignKey(
        DocumentFlow,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    template = models.ForeignKey(
        "dsign.DocuSignTemplate",
        on_delete=models.CASCADE,
        related_name="flow_steps",
    )
    step_order = models.PositiveIntegerField()
    label = models.CharField(max_length=255, blank=True)

    is_required = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["step_order"]
        unique_together = [
            ("flow", "step_order"),
        ]
        
    def __str__(self):
        return f"{self.flow.name} - Step {self.step_order} - {self.display_name}"

    @property
    def display_name(self):
        return self.label or self.template.template_name


class SentDocuSignEnvelope(models.Model):
    STATUS_CHOICES = [
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("completed", "Completed"),
        ("declined", "Declined"),
        ("voided", "Voided"),
    ]

    employer = models.ForeignKey(
        "user.Employer",
        on_delete=models.CASCADE,
        related_name="sent_docusign_envelopes",
    )
    user = models.ForeignKey(
        "user.CustomUser",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sent_docusign_envelopes",
    )
    template = models.ForeignKey(
        "dsign.DocuSignTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_envelopes",
    )
    flow = models.ForeignKey(
        "documentflow.DocumentFlow",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_envelopes",
    )
    flow_step = models.ForeignKey(
        "documentflow.DocumentFlowStep",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_envelopes",
    )
    template_name = models.CharField(max_length=255, blank=True)
    envelope_id = models.CharField(max_length=255, unique=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="sent",
    )

    sent_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return f"{self.template_name or self.template} - {self.user} - {self.status}"


class SentDocuSignRecipient(models.Model):
    STATUS_CHOICES = [
        ("created", "Created"),
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("completed", "Completed"),
        ("declined", "Declined"),
        ("voided", "Voided"),
    ]

    sent_envelope = models.ForeignKey(
        "documentflow.SentDocuSignEnvelope",
        on_delete=models.CASCADE,
        related_name="recipients",
    )

    recipient_id = models.CharField(max_length=50, blank=True)
    recipient_id_guid = models.CharField(max_length=255, blank=True)

    role_name = models.CharField(max_length=100, blank=True)
    name = models.CharField(max_length=255, blank=True)
    email = models.EmailField()

    routing_order = models.PositiveIntegerField(default=1)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="created",
    )

    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["routing_order", "id"]
        unique_together = [("sent_envelope", "recipient_id")]

    def __str__(self):
        label = self.role_name or self.email
        return f"{label} - {self.status}"