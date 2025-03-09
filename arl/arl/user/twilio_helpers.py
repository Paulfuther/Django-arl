import logging
from twilio.rest import Client
from django.conf import settings
from arl.setup.models import TenantApiKeys

logger = logging.getLogger(__name__)


def create_twilio_subaccount(employer):
    """
    Create a Twilio subaccount for the new Employer.
    """
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        # ✅ Create Twilio Subaccount
        subaccount = client.api.accounts.create(friendly_name=employer.name)
        sub_sid, sub_auth_token = subaccount.sid, subaccount.auth_token

        logger.info(f"✅ Twilio subaccount created for {employer.name}: {sub_sid}")

        # ✅ Purchase Phone Number
        phone_number = purchase_twilio_phone_number(sub_sid, sub_auth_token)
        if not phone_number:
            logger.error("🚨 No phone number assigned, stopping Twilio setup.")
            return None

        # ✅ Create Messaging & Notify Services
        messaging_sid = create_twilio_messaging_service(sub_sid, sub_auth_token, employer.name)
        notify_sid = create_twilio_notify_service(sub_sid, sub_auth_token, employer.name)

        # ✅ Store Twilio details
        TenantApiKeys.objects.create(
            employer=employer,
            account_sid=sub_sid,
            auth_token=sub_auth_token,
            phone_number=phone_number,
            messaging_service_sid=messaging_sid,
            notify_service_sid=notify_sid
        )

        logger.info(f"✅ Twilio setup complete for {employer.name}")

    except Exception as e:
        logger.error(f"🚨 Error creating Twilio subaccount: {str(e)}")


def purchase_twilio_phone_number(sub_sid, sub_auth_token):
    """
    Purchase a Twilio phone number.
    """
    try:
        sub_client = Client(sub_sid, sub_auth_token)

        available_numbers = sub_client.available_phone_numbers("CA").local.list(limit=1)
        if not available_numbers:
            logger.error("🚨 No available phone numbers.")
            return None

        purchased_number = sub_client.incoming_phone_numbers.create(
            phone_number=available_numbers[0].phone_number
        )

        logger.info(f"✅ Purchased Twilio phone number: {purchased_number.phone_number}")
        return purchased_number.phone_number

    except Exception as e:
        logger.error(f"🚨 Error purchasing phone number: {str(e)}")
        return None


def create_twilio_messaging_service(sub_sid, sub_auth_token, employer_name):
    """
    Create a Twilio Messaging Service.
    """
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
    """
    Create a Twilio Notify Service.
    """
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