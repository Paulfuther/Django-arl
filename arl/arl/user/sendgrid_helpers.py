import logging
import requests
from django.conf import settings
from arl.setup.models import TenantApiKeys

logger = logging.getLogger(__name__)

SENDGRID_API_KEY = settings.SENDGRID_API_KEY
SENDGRID_SENDER_VERIFICATION_URL = settings.SENDGRID_SENDER_VERIFICATION_URL


def add_sendgrid_verified_sender(employer):
    """
    Create a verified sender in SendGrid for the employer.
    """
    if not employer.verified_sender_email:
        logger.error("❌ Missing verified sender email. Cannot proceed.")
        return False

    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "nickname": employer.senior_contact_name,
        "from_email": employer.verified_sender_email,
        "from_name": employer.name,
        "reply_to": employer.verified_sender_email,
        "address": employer.address or "123 Default St",
        "city": employer.city or "Default City",
        "country": employer.country.code if employer.country else "CA",
    }

    response = requests.post(
        SENDGRID_SENDER_VERIFICATION_URL, json=data, headers=headers
    )

    if response.status_code == 201:
        logger.info(
            f"✅ SendGrid verified sender added: {employer.verified_sender_email}"
        )

        # ✅ Check if a `TenantApiKeys` entry exists for this employer
        tenant_api_key, created = TenantApiKeys.objects.get_or_create(
            employer=employer,
            defaults={"verified_sender_email": employer.verified_sender_email},
        )

        if not created:
            tenant_api_key.sender_email = (
                employer.verified_sender_email
            )  # ✅ Update existing
            tenant_api_key.save(update_fields=["verified_sender_email"])

        return True

    elif response.status_code == 400 and "already exists" in response.text:
        logger.warning(
            f"⚠️ SendGrid sender {employer.verified_sender_email} already exists."
        )

        # ✅ Ensure it is stored in TenantApiKeys even if it already exists in SendGrid
        tenant_api_key, created = TenantApiKeys.objects.get_or_create(
            employer=employer,
            defaults={"verified_sender_email": employer.verified_sender_email},
        )

        if not created:
            tenant_api_key.verified_sender_email = (
                employer.verified_sender_email
            )  # ✅ Update if necessary
            tenant_api_key.save(update_fields=["verified_sender_email"])

        return True

    else:
        logger.error(f"❌ Failed to add SendGrid sender: {response.json()}")
        return False
