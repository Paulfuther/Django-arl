from __future__ import absolute_import, unicode_literals

from twilio.rest import Client
from django.conf import settings
import logging
from .models import TenantApiKeys
from arl.celery import app


logger = logging.getLogger(__name__)


@app.task(name="setup_twilio_for_employer")
def setup_twilio_for_employer(employer_id):
    """
    Celery task to set up Twilio services for a new employer.
    """
    from .models import Employer  # Avoid circular import

    try:
        employer = Employer.objects.get(id=employer_id)
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        # ✅ Create Twilio Subaccount
        subaccount = client.api.accounts.create(friendly_name=employer.name)
        sub_sid, sub_auth_token = subaccount.sid, subaccount.auth_token

        logger.info(f"✅ Twilio subaccount created for {employer.name}: {sub_sid}")

        # ✅ Purchase Phone Number
        phone_number_sid, phone_number = purchase_twilio_phone_number(sub_sid, sub_auth_token)
        if not phone_number_sid:
            logger.error("🚨 No phone number assigned, stopping Twilio setup.")
            return None

        # ✅ Create Messaging & Notify Services
        messaging_sid = create_twilio_messaging_service(sub_sid, sub_auth_token, employer.name)
        notify_sid = create_twilio_notify_service(sub_sid, sub_auth_token, employer.name)

        # ✅ Assign the phone number to the Messaging Service
        assign_number_to_messaging_service(sub_sid, sub_auth_token, phone_number_sid, messaging_sid)

        # ✅ Link Notify Service to Messaging Service
        link_notify_service_to_messaging(sub_sid, sub_auth_token, notify_sid, messaging_sid)

        # ✅ Store Twilio credentials in TenantApiKeys
        tenant_api_key, created = TenantApiKeys.objects.get_or_create(
            employer=employer,
            defaults={
                "account_sid": sub_sid,
                "auth_token": sub_auth_token,
                "phone_number": phone_number,
                "phone_number_sid": phone_number_sid,
                "messaging_service_sid": messaging_sid,
                "notify_service_sid": notify_sid
            }
        )

        if not created:
            tenant_api_key.account_sid = sub_sid
            tenant_api_key.auth_token = sub_auth_token
            tenant_api_key.phone_number = phone_number
            tenant_api_key.phone_number_sid = phone_number_sid
            tenant_api_key.messaging_service_sid = messaging_sid
            tenant_api_key.notify_service_sid = notify_sid
            tenant_api_key.save(update_fields=[
                "account_sid", "auth_token", "phone_number", "messaging_service_sid", "notify_service_sid"
            ])

        logger.info(f"✅ Twilio setup complete for {employer.name}")

    except Exception as e:
        logger.error(f"🚨 Error creating Twilio subaccount: {str(e)}")


def purchase_twilio_phone_number(sub_sid, sub_auth_token):
    """Purchases a Twilio phone number and returns (phone_number_sid, phone_number)."""
    try:
        client = Client(sub_sid, sub_auth_token)

        # ✅ Search for a Canadian number
        available_numbers = client.available_phone_numbers("CA").local.list(limit=1)

        if not available_numbers:
            logger.error("🚨 No available Twilio numbers in CA.")
            return None, None

        # ✅ Buy the first available number
        purchased_number = client.incoming_phone_numbers.create(
            phone_number=available_numbers[0].phone_number
        )

        logger.info(f"✅ Purchased Twilio number: {purchased_number.phone_number}")
        return purchased_number.sid, purchased_number.phone_number

    except Exception as e:
        logger.error(f"❌ Failed to purchase Twilio number: {str(e)}")
        return None, None


def create_twilio_messaging_service(sub_sid, sub_auth_token, employer_name):
    """Create a Twilio Messaging Service."""
    try:
        sub_client = Client(sub_sid, sub_auth_token)

        messaging_service = sub_client.messaging.services.create(
            friendly_name=f"{employer_name} Messaging"
        )

        logger.info(f"✅ Messaging Service created: {messaging_service.sid}")
        return messaging_service.sid

    except Exception as e:
        logger.error(f"🚨 Error creating Messaging Service: {str(e)}")
        return None


def create_twilio_notify_service(sub_sid, sub_auth_token, employer_name):
    """Create a Twilio Notify Service."""
    try:
        sub_client = Client(sub_sid, sub_auth_token)

        notify_service = sub_client.notify.services.create(
            friendly_name=f"{employer_name} Notify"
        )

        logger.info(f"✅ Notify Service created: {notify_service.sid}")
        return notify_service.sid

    except Exception as e:
        logger.error(f"🚨 Error creating Notify Service: {str(e)}")
        return None


def assign_number_to_messaging_service(sub_sid, sub_auth_token, phone_number_sid, messaging_sid):
    """Assigns a Twilio phone number to a Messaging Service."""
    try:
        client = Client(sub_sid, sub_auth_token)

        client.messaging.services(messaging_sid).phone_numbers.create(
            phone_number_sid=phone_number_sid
        )

        logger.info(f"✅ Phone number {phone_number_sid} linked to Messaging Service {messaging_sid}")

    except Exception as e:
        logger.error(f"❌ Failed to link phone number to Messaging Service: {str(e)}")


def link_notify_service_to_messaging(sub_sid, sub_auth_token, notify_sid, messaging_sid):
    """Links a Notify Service to a Messaging Service."""
    try:
        client = Client(sub_sid, sub_auth_token)

        client.notify.services(notify_sid).update(
            messaging_service_sid=messaging_sid
        )

        logger.info(f"✅ Notify Service {notify_sid} linked to Messaging Service {messaging_sid}")

    except Exception as e:
        logger.error(f"❌ Failed to link Notify Service to Messaging Service: {str(e)}")