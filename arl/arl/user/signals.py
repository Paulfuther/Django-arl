
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Employer
from django.conf import settings


from arl.user.models import EmployerRequest
from arl.setup.tasks import setup_twilio_for_employer
from arl.user.sendgrid_helpers import add_sendgrid_verified_sender


logger = logging.getLogger(__name__)
SENDGRID_API_KEY = settings.SENDGRID_API_KEY
SENDGRID_SENDER_VERIFICATION_URL = settings.SENDGRID_SENDER_VERIFICATION_URL


# Once you approve a request from the employer request model
# a new Employer is created
@receiver(post_save, sender=Employer)
def handle_new_employer(sender, instance, created, **kwargs):
    """
    Set up SendGrid and Twilio when a new Employer is created.
    """
    if not created:
        return

    logger.info(f"📢 New Employer added: {instance.name}")

    # ✅ Ensure `verified_sender_email` is generated
    if not instance.verified_sender_email and instance.senior_contact_name:
        instance.verified_sender_local = instance.senior_contact_name.lower().replace(" ", "").replace(".", "")
        instance.verified_sender_email = f"{instance.verified_sender_local}@1553690ontarioinc.com"
        instance.save()

    # ✅ Add SendGrid Verified Sender
    if add_sendgrid_verified_sender(instance):
        # ✅ Proceed with Twilio setup **only if SendGrid is successful**
        setup_twilio_for_employer.delay(instance.id)


@receiver(post_save, sender=EmployerRequest)
def approve_employer(sender, instance, created, **kwargs):
    if instance.status == "approved":
        employer, created = Employer.objects.get_or_create(
            name=instance.name,
            email=instance.email,
            phone_number=instance.phone_number
        )
        # ✅ Send email with Stripe payment link
        # send_payment_email(employer)