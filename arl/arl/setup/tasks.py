from __future__ import absolute_import, unicode_literals

import logging
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from django.utils.crypto import get_random_string
from twilio.rest import Client

from arl.celery import app
from arl.msg.helpers import create_master_email
from arl.user.models import ErrorLog, NewHireInvite
from arl.user.sendgrid_helpers import add_sendgrid_verified_sender

from .models import Employer, EmployerRequest, StripePayment, TenantApiKeys

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
        phone_number_sid, phone_number = purchase_twilio_phone_number(
            sub_sid, sub_auth_token
        )
        if not phone_number_sid:
            logger.error("🚨 No phone number assigned, stopping Twilio setup.")
            return None

        # ✅ Create Messaging & Notify Services
        messaging_sid = create_twilio_messaging_service(
            sub_sid, sub_auth_token, employer.name
        )
        notify_sid = create_twilio_notify_service(
            sub_sid, sub_auth_token, employer.name
        )

        # ✅ Assign the phone number to the Messaging Service
        assign_number_to_messaging_service(
            sub_sid, sub_auth_token, phone_number_sid, messaging_sid
        )

        # ✅ Link Notify Service to Messaging Service
        link_notify_service_to_messaging(
            sub_sid, sub_auth_token, notify_sid, messaging_sid
        )

        # ✅ Store Twilio credentials in TenantApiKeys
        tenant_api_key, created = TenantApiKeys.objects.get_or_create(
            employer=employer,
            defaults={
                "account_sid": sub_sid,
                "auth_token": sub_auth_token,
                "phone_number": phone_number,
                "phone_number_sid": phone_number_sid,
                "messaging_service_sid": messaging_sid,
                "notify_service_sid": notify_sid,
            },
        )

        if not created:
            tenant_api_key.account_sid = sub_sid
            tenant_api_key.auth_token = sub_auth_token
            tenant_api_key.phone_number = phone_number
            tenant_api_key.phone_number_sid = phone_number_sid
            tenant_api_key.messaging_service_sid = messaging_sid
            tenant_api_key.notify_service_sid = notify_sid
            tenant_api_key.save(
                update_fields=[
                    "account_sid",
                    "auth_token",
                    "phone_number",
                    "messaging_service_sid",
                    "notify_service_sid",
                ]
            )

        logger.info(f"✅ Twilio setup complete for {employer.name}")

    except Exception as e:
        logger.error(f"🚨 Error creating Twilio subaccount: {str(e)}")

        # 🧠 Log the failure to ErrorLog
        ErrorLog.objects.create(
            path="setup_twilio_for_employer",
            method="TASK",
            status_code=500,
            error_message=f"Twilio setup failed for Employer ID {employer_id}: {str(e)}",
        )


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


def assign_number_to_messaging_service(
    sub_sid, sub_auth_token, phone_number_sid, messaging_sid
):
    """Assigns a Twilio phone number to a Messaging Service."""
    try:
        client = Client(sub_sid, sub_auth_token)

        client.messaging.services(messaging_sid).phone_numbers.create(
            phone_number_sid=phone_number_sid
        )

        logger.info(
            f"✅ Phone number {phone_number_sid} linked to Messaging Service {messaging_sid}"
        )

    except Exception as e:
        logger.error(f"❌ Failed to link phone number to Messaging Service: {str(e)}")


def link_notify_service_to_messaging(
    sub_sid, sub_auth_token, notify_sid, messaging_sid
):
    """Links a Notify Service to a Messaging Service."""
    try:
        client = Client(sub_sid, sub_auth_token)

        client.notify.services(notify_sid).update(messaging_service_sid=messaging_sid)

        logger.info(
            f"✅ Notify Service {notify_sid} linked to Messaging Service {messaging_sid}"
        )

    except Exception as e:
        logger.error(f"❌ Failed to link Notify Service to Messaging Service: {str(e)}")


@app.task(name="post_stripe_payment_setup")
def post_stripe_payment_setup(
    employer_request_id, session_id=None, subscription_id=None, customer_id=None
):
    try:
        employer_request = EmployerRequest.objects.get(id=employer_request_id)

        # Prevent duplicate employer creation
        if Employer.objects.filter(email=employer_request.email).exists():
            warning_msg = f"Employer with email {employer_request.email} already exists. Skipping creation."
            logger.warning(warning_msg)
            ErrorLog.objects.create(
                path="post_stripe_payment_setup",
                method="TASK",
                status_code=400,
                error_message=warning_msg,
            )
            return

        # Generate sender email
        verified_sender_local = (
            (employer_request.verified_sender_local or employer_request.name)
            .lower()
            .replace(" ", "")
            .replace(".", "")
        )
        verified_sender_email = f"{verified_sender_local}@1553690ontarioinc.com"

        # Create employer
        employer = Employer.objects.create(
            name=employer_request.company_name,
            email=employer_request.email,
            phone_number=employer_request.phone_number,
            address=employer_request.address,
            city=employer_request.city,
            state_province=employer_request.state_province,
            country=employer_request.country,
            senior_contact_name=f"{employer_request.senior_contact_first_name} {employer_request.senior_contact_last_name}",
            verified_sender_local=verified_sender_local,
            verified_sender_email=verified_sender_email,
            is_active=True,
        )
        logger.info(f"✅ Employer created: {employer.name}")

        # Record Stripe payment
        StripePayment.objects.create(
            employer=employer,
            amount=employer_request.stripe_plan.amount
            if employer_request.stripe_plan
            else Decimal("0.00"),
            is_paid=True,
            payment_date=timezone.now(),
            stripe_session_id=session_id,
            stripe_subscription_id=subscription_id,
            stripe_customer_id=customer_id,
        )
        logger.info(f"✅ Stripe payment recorded for employer: {employer.name}")

        # ✅ Add SendGrid Verified Sender (must happen before invite)
        if add_sendgrid_verified_sender(employer):
            logger.info(f"✅ Verified sender setup complete for {employer.name}")

            # ✅ Send invite only if sender is verified
            existing_invite = NewHireInvite.objects.filter(
                email=employer.email, used=False
            ).first()
            if not existing_invite:
                invite_token = get_random_string(64)
                invite = NewHireInvite.objects.create(
                    employer=employer,
                    email=employer.email,
                    name=employer.name,
                    role="EMPLOYER",
                    token=invite_token,
                )
                logger.info(f"📩 Invite created for employer: {invite.token}")
            else:
                invite = existing_invite

            # ✅ Send registration email
            sendgrid_template_id = settings.SENDGRID_EMPLOYER_REGISTER_AS_USER
            invite_link = f"{settings.SITE_URL}/register/{invite.token}/"
            email_data = {
                "to_email": employer.email,
                "sendgrid_id": sendgrid_template_id,
                "template_data": {
                    "employer_name": employer.senior_contact_name,
                    "company_name": employer.name,
                    "invite_link": invite_link,
                    "sender_contact_name": "Support Team",
                },
                "verified_sender": employer.verified_sender_email,
            }

            create_master_email(**email_data)
            logger.info(f"✅ Invite email sent to {employer.email}")

            # ✅ Kick off Twilio setup
            setup_twilio_for_employer.delay(employer.id)
            logger.info(f"✅ Twilio setup triggered for {employer.name}")

        else:
            error_message = f"❌ Failed to verify sender for employer {employer.name}"
            logger.warning(error_message)
            ErrorLog.objects.create(
                path="post_stripe_payment_setup",
                method="TASK",
                status_code=500,
                error_message=error_message,
            )

    except EmployerRequest.DoesNotExist:
        msg = f"❌ EmployerRequest with id {employer_request_id} not found."
        logger.error(msg)
        ErrorLog.objects.create(
            path="post_stripe_payment_setup",
            method="TASK",
            status_code=404,
            error_message=msg,
        )

    except Exception as e:
        error_msg = f"🚨 Unexpected error in post_stripe_payment_setup: {str(e)}"
        logger.exception(error_msg)
        ErrorLog.objects.create(
            path="post_stripe_payment_setup",
            method="TASK",
            status_code=500,
            error_message=error_msg,
        )
