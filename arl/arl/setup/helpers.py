import os
from arl.user.models import TenantAPIKeys


def get_tenant_api_keys(employer):
    """
    Returns a dictionary of API keys for a given employer.
    Falls back to environment variables if no keys exist.
    """
    keys = TenantAPIKeys.objects.filter(employer=employer).first()
    
    if not keys:
        return {
            "twilio_account_sid": os.getenv("TWILIO_ACCOUNT_SID"),
            "twilio_auth_token": os.getenv("TWILIO_AUTH_TOKEN"),
            "twilio_service_sid": os.getenv("TWILIO_SERVICE_SID"),
            "sendgrid_api_key": os.getenv("SENDGRID_API_KEY"),
            "dropbox_access_token": os.getenv("DROPBOX_ACCESS_TOKEN"),
        }

    return {
        "twilio_account_sid": keys.twilio_account_sid or os.getenv("TWILIO_ACCOUNT_SID"),
        "twilio_auth_token": keys.twilio_auth_token or os.getenv("TWILIO_AUTH_TOKEN"),
        "twilio_service_sid": keys.twilio_service_sid or os.getenv("TWILIO_SERVICE_SID"),
        "sendgrid_api_key": keys.sendgrid_api_key or os.getenv("SENDGRID_API_KEY"),
        "dropbox_access_token": keys.dropbox_access_token or os.getenv("DROPBOX_ACCESS_TOKEN"),
    }