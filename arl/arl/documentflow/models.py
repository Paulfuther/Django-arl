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
        unique_together = ("flow", "step_order")
        unique_together = ("flow", "template", "step_order")

    def __str__(self):
        return f"{self.flow.name} - Step {self.step_order} - {self.display_name}"

    @property
    def display_name(self):
        return self.label or self.template.template_name