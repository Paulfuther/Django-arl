from django.contrib import admin
from .models import ComplianceFile, EmailEvent
from django.utils.html import format_html
from arl.bucket.helpers import upload_to_linode_object_storage  # adjust if needed
from uuid import uuid4
from django.conf import settings
import boto3


@admin.register(ComplianceFile)
class ComplianceFileAdmin(admin.ModelAdmin):
    list_display = ("title", "uploaded_at", "is_active", "presigned_link_display")
    list_filter = ("is_active",)
    search_fields = ("title",)
    readonly_fields = ("s3_key", "presigned_url", "uploaded_at")

    def presigned_link_display(self, obj):
        if obj.presigned_url:
            return format_html('<a href="{}" target="_blank">View File</a>', obj.presigned_url)
        return "-"
    presigned_link_display.short_description = "Download Link"

    def save_model(self, request, obj, form, change):
        if obj.is_active:
            ComplianceFile.objects.exclude(pk=obj.pk).update(is_active=False)

        super().save_model(request, obj, form, change)

        if obj.file and not obj.s3_key:
            key = f"compliance/{uuid4()}_{obj.file.name}"
            upload_to_linode_object_storage(obj.file.file, key)
            obj.s3_key = key

            # ✅ Generate new presigned URL
            conn = boto3.client(
                "s3",
                endpoint_url=settings.LINODE_ENDPOINT,
                aws_access_key_id=settings.LINODE_ACCESS_KEY,
                aws_secret_access_key=settings.LINODE_SECRET_KEY,
                region_name="us-east-1",
            )
            obj.presigned_url = conn.generate_presigned_url(
                ClientMethod='get_object',
                Params={'Bucket': settings.LINODE_BUCKET_NAME, 'Key': key},
                ExpiresIn=60 * 60 * 24 * 7
            )

            obj.save(update_fields=["s3_key", "presigned_url"])

@admin.register(EmailEvent)
class EmailEventAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "email", "event", "subject", "sg_template_name", "employer")
    list_filter = ("event", "employer", "sg_template_name", "timestamp")
    search_fields = ("email", "subject", "sg_template_name", "sg_message_id", "sg_event_id")
    ordering = ("-timestamp",)