import os
import uuid

import boto
import boto.s3.connection
from django.conf import settings
from django.db import models
import logging

logger = logging.getLogger(__name__)


def recruit_resume_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    safe_ext = ext if ext in [".pdf", ".doc", ".docx"] else ".pdf"

    if not getattr(instance, "resume_folder", None):
        instance.resume_folder = str(uuid.uuid4())

    return f"recruit/resumes/{instance.resume_folder}/{uuid.uuid4()}{safe_ext}"


class RecruitApplicant(models.Model):
    STATUS_CHOICES = [
        ("new", "New"),
        ("contacted", "Contacted"),
        ("screening", "Screening"),
        ("interview", "Interview"),
        ("offered", "Offered"),
        ("hired", "Hired"),
        ("rejected", "Rejected"),
        ("archived", "Archived"),
    ]

    EMPLOYMENT_TYPE_CHOICES = [
        ("full_time", "Full Time"),
        ("part_time", "Part Time"),
        ("either", "Either"),
    ]

    SOURCE_CHOICES = [
        ("linkedin", "LinkedIn"),
        ("instagram", "Instagram"),
        ("facebook", "Facebook"),
        ("whatsapp", "WhatsApp"),
        ("referral", "Referral"),
        ("direct", "Direct"),
        ("other", "Other"),
    ]

    employer = models.ForeignKey(
        "user.Employer",
        on_delete=models.CASCADE,
        related_name="recruit_applicants",
        null=True,
        blank=True,
    )

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=30)
    city = models.CharField(max_length=150, blank=True)
    position_interest = models.CharField(max_length=255, blank=True)

    employment_type = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_TYPE_CHOICES,
        default="either",
    )

    availability = models.TextField(blank=True)
    has_transportation = models.BooleanField(default=False)
    eligible_to_work_in_canada = models.BooleanField(default=False)

    linkedin_profile = models.URLField(blank=True)
    source = models.CharField(
        max_length=30,
        choices=SOURCE_CHOICES,
        default="direct",
    )

    resume_folder = models.CharField(max_length=255, blank=True, default=uuid.uuid4)
    resume_original_name = models.CharField(max_length=255, blank=True)
    resume_object_key = models.CharField(max_length=500, blank=True)

    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="new",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.status}"

    def _generate_signed_resume_url(self, expires=300, download=False):
        """
        Generate a temporary signed URL for the resume.
        If download=True, force browser download.
        """
        if not self.resume_object_key:
            return ""

        try:
            conn = boto.connect_s3(
                aws_access_key_id=settings.LINODE_ACCESS_KEY,
                aws_secret_access_key=settings.LINODE_SECRET_KEY,
                host=settings.LINODE_REGION,
                calling_format=boto.s3.connection.OrdinaryCallingFormat(),
            )

            bucket = conn.get_bucket(settings.LINODE_BUCKET_NAME)
            key = bucket.get_key(self.resume_object_key)

            if not key:
                return ""

            if download:
                filename = self.resume_original_name or "resume"
                return key.generate_url(
                    expires,
                    query_auth=True,
                    response_headers={
                        "response-content-disposition": f'attachment; filename="{filename}"'
                    },
                )

            return key.generate_url(expires)

        except Exception:
            logger.exception("Error generating signed URL for applicant resume")
            return ""

    def get_signed_resume_view_url(self):
        return self._generate_signed_resume_url(expires=300, download=False)

    def get_signed_resume_download_url(self):
        return self._generate_signed_resume_url(expires=300, download=True)