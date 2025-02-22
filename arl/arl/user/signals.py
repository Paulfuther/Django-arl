import requests
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Employer
from django.conf import settings
from arl.msg.helpers import client
from arl.setup.models import TenantApiKeys
from twilio.rest import Client

logger = logging.getLogger(__name__)
SENDGRID_API_KEY = settings.SENDGRID_API_KEY
SENDGRID_SENDER_VERIFICATION_URL = "https://api.sendgrid.com/v3/verified_senders"


@receiver(post_save, sender=Employer)
def handle_new_employer(sender, instance, created, **kwargs):
    """
    Signal to create a SendGrid verified sender and Twilio subaccount
    when a new Employer is added.
    """
    if created:
        logger.info(f"📢 New Employer added: {instance.name}")

        # ✅ Step 1: Generate verified sender email if not set
        if not instance.verified_sender_email:
            instance.verified_sender_email = f"{instance.name.lower().replace(' ', '')}@1553690ontarioinc.com"
            instance.save(update_fields=["verified_sender_email"])
            logger.info(f"Generated verified sender: {instance.verified_sender_email}")

        # ✅ Step 2: Add Verified Sender to SendGrid
        headers = {
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json",
        }
        data = {
            "nickname": instance.name,
            "from_email": instance.verified_sender_email,
            "from_name": instance.name,
            "reply_to": instance.verified_sender_email,
            "address": instance.address or "123 Default St",
            "city": instance.city or "Default City",
            "country": instance.country.code if instance.country else "CA",
        }

        response = requests.post(SENDGRID_SENDER_VERIFICATION_URL, json=data, headers=headers)

        if response.status_code == 201:
            logger.info(f"✅ SendGrid verified sender added: {instance.verified_sender_email}")

            # ✅ Store Verified Sender in `TenantApiKeys`
            TenantApiKeys.objects.create(
                employer=instance,
                service_name="sendgrid",
                sender_email=instance.verified_sender_email
            )
            logger.info(f"✅ Sender email stored in TenantApiKeys: {instance.verified_sender_email}")
            
        elif response.status_code == 400 and "already exists" in response.text:
            logger.warning(f"⚠️ SendGrid sender {instance.verified_sender_email} already exists.")
        else:
            logger.error(f"❌ Failed to add SendGrid sender: {response.json()}")

        # ✅ Step 3: Create Twilio Subaccount for Employer
        create_twilio_subaccount(instance)


def create_twilio_subaccount(employer):
    """
    Create a Twilio subaccount for the new Employer.
    """
    try:
        subaccount = client.api.accounts.create(friendly_name=employer.name)

        # ✅ Purchase Twilio Phone Number
        phone_number = purchase_twilio_phone_number(subaccount.sid, subaccount.auth_token, employer.name)

        # ✅ Create Twilio Messaging Service
        messaging_service_sid = create_twilio_messaging_service(subaccount.sid, subaccount.auth_token, employer.name)

        # ✅ Store Twilio Subaccount SID, Auth Token, and Messaging Service SID in TenantApiKeys
        TenantApiKeys.objects.create(
            employer=employer,
            service_name="twilio",
            account_sid=subaccount.sid,
            auth_token=subaccount.auth_token,
            phone_number=phone_number,
            messaging_service_sid=messaging_service_sid  # ✅ Store Messaging Service
        )

        logger.info(f"✅ Twilio subaccount created for {employer.name}: {subaccount.sid}")
        logger.info(f"✅ Twilio phone number {phone_number} assigned to {employer.name}")
        logger.info(f"✅ Twilio Messaging Service created: {messaging_service_sid}")

    except Exception as e:
        logger.error(f"🚨 Error creating Twilio subaccount for {employer.name}: {str(e)}")


def create_twilio_messaging_service(subaccount_sid, subaccount_auth_token, employer_name):
    """
    Create a Twilio Messaging Service for a subaccount.
    """
    try:
        subaccount_client = Client(subaccount_sid, subaccount_auth_token)

        # ✅ Create the Messaging Service
        messaging_service = subaccount_client.messaging.services.create(
            friendly_name=f"{employer_name} Messaging"
        )

        logger.info(f"✅ Messaging Service created: {messaging_service.sid}")

        return messaging_service.sid

    except Exception as e:
        logger.error(f"🚨 Error creating Messaging Service: {str(e)}")
        return None


def purchase_twilio_phone_number(subaccount_sid, subaccount_auth_token, employer_name):
    """
    Purchase a Twilio phone number for a subaccount and assign it to a Messaging Service.
    """
    try:
        subaccount_client = Client(subaccount_sid, subaccount_auth_token)

        # ✅ Search for available phone numbers
        available_numbers = subaccount_client.available_phone_numbers("CA").local.list(limit=1)
        if not available_numbers:
            logger.error("🚨 No available phone numbers found.")
            return None

        # ✅ Purchase the first available number
        purchased_number = subaccount_client.incoming_phone_numbers.create(
            phone_number=available_numbers[0].phone_number
        )

        logger.info(f"✅ Purchased Twilio phone number: {purchased_number.phone_number}")

        return purchased_number.phone_number

    except Exception as e:
        logger.error(f"🚨 Error purchasing Twilio phone number: {str(e)}")
        return None
