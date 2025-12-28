import uuid
from pathlib import Path

# app: checks/models.py
from django.conf import settings
from django.db import models
from django.utils.text import slugify

from arl.user.models import CustomUser, Employer

User = settings.AUTH_USER_MODEL


class Quiz(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, related_name="questions", on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.text


class Answer(models.Model):
    question = models.ForeignKey(
        Question, related_name="answers", on_delete=models.CASCADE
    )
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text


class SaltLog(models.Model):
    user = models.ForeignKey(
        CustomUser, null=True, on_delete=models.CASCADE, related_name="salt_log"
    )
    store = models.ForeignKey("user.Store", on_delete=models.CASCADE)
    area_salted = models.CharField(max_length=255)
    date_salted = models.DateField(null=True)
    time_salted = models.TimeField(null=True)  # Add time field
    hidden_timestamp = models.DateTimeField(auto_now_add=True)
    image_folder = models.CharField(max_length=255, null=True)
    user_employer = models.ForeignKey(Employer, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Salt Log {self.pk} for {self.user.first_name} {self.user.last_name}"


def checklist_photo_upload_to(instance, filename):
    # /checklists/<checklist_id>/<item_uuid>/<originalname>
    return str(
        Path("checklists")
        / str(instance.checklist_id or "unassigned")
        / str(instance.uuid)
        / filename
    )


class ChecklistTemplate(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_checklist_templates",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class ChecklistTemplateItem(models.Model):
    template = models.ForeignKey(
        ChecklistTemplate, on_delete=models.CASCADE, related_name="items"
    )
    text = models.CharField(max_length=500)
    requires_photo = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.template.name} » {self.text}"


class Checklist(models.Model):
    STATUS = (
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("completed", "Completed (PDF generated)"),
    )

    template = models.ForeignKey(
        ChecklistTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checklists",
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, editable=False)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_checklists"
    )
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_checklists",
    )
    status = models.CharField(max_length=20, choices=STATUS, default="draft")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    store = models.ForeignKey(
        "user.Store",  # or "yourapp.Store" — use the correct app label
        on_delete=models.PROTECT,
        null=True,  # set null=True for the first migration to avoid breaking existing rows
        blank=True,
        related_name="checklists",
    )
    pdf_file = models.FileField(
        upload_to="checklists/pdfs/", null=True, blank=True
    )  # optionally swap to Linode/S3 Storage

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title) or "checklist"
            self.slug = f"{base}-{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)


class ChecklistItem(models.Model):
    RESULT = (
        ("yes", "Yes"),
        ("no", "No"),
        ("na", "N/A"),
    )

    checklist = models.ForeignKey(
        Checklist, on_delete=models.CASCADE, related_name="items"
    )
    template_item = models.ForeignKey(
        ChecklistTemplateItem, on_delete=models.SET_NULL, null=True, blank=True
    )
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    text = models.CharField(max_length=500)  # store a copy for audit
    result = models.CharField(max_length=5, choices=RESULT, default="no")
    comment = models.TextField(blank=True)
    photo = models.ImageField(
        upload_to=checklist_photo_upload_to,
        blank=True,
        null=True,
        max_length=512,
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.checklist.title} » {self.text[:40]}"
