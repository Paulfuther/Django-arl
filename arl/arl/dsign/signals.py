from .models import ProcessedDocsignDocument
from django.db.models.signals import post_save
from django.dispatch import receiver
from arl.dsign.models import DocuSignTemplate
from .tasks import (send_new_hire_quiz,
                    upload_signed_document_to_linode,
                    notify_hr, fetch_and_upload_signed_documents)
import logging


logger = logging.getLogger(__name__)


@receiver(post_save, sender=ProcessedDocsignDocument)
def post_save_processed_docsign_document(sender, instance, created, **kwargs):
    """Handles actions when a signed DocuSign document is saved."""
    if created:
        logger.info(f"📂 New signed document detected: {instance.template_name} for {instance.user.email}")

     
        logger.info(f"📨 Sent HR notification for signed document: {instance.template_name}")