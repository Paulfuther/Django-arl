import os
from functools import wraps

from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string

from .models import TenantApiKeys


def get_tenant_api_keys(employer):
    """
    Returns a dictionary of API keys for a given employer.
    Falls back to environment variables if no keys exist.
    """
    keys = TenantApiKeys.objects.filter(employer=employer).first()

    if not keys:
        return {
            "twilio_account_sid": os.getenv("TWILIO_ACCOUNT_SID"),
            "twilio_auth_token": os.getenv("TWILIO_AUTH_TOKEN"),
            "twilio_service_sid": os.getenv("TWILIO_SERVICE_SID"),
            "sendgrid_api_key": os.getenv("SENDGRID_API_KEY"),
            "dropbox_access_token": os.getenv("DROPBOX_ACCESS_TOKEN"),
        }

    return {
        "twilio_account_sid": keys.twilio_account_sid
        or os.getenv("TWILIO_ACCOUNT_SID"),
        "twilio_auth_token": keys.twilio_auth_token or os.getenv("TWILIO_AUTH_TOKEN"),
        "twilio_service_sid": keys.twilio_service_sid
        or os.getenv("TWILIO_SERVICE_SID"),
        "sendgrid_api_key": keys.sendgrid_api_key or os.getenv("SENDGRID_API_KEY"),
        "dropbox_access_token": keys.dropbox_access_token
        or os.getenv("DROPBOX_ACCESS_TOKEN"),
    }


def employer_hr_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if (
            request.user.is_authenticated
            and request.user.groups.filter(name__in=["EMPLOYER", "Manager"]).exists()
        ):
            return view_func(request, *args, **kwargs)

        if request.headers.get("Hx-Request") == "true":
            html = render_to_string("incident/403.html", request=request)
            return HttpResponse(html, status=403)
        else:
            return render(request, "incident/403.html", status=403)

    return _wrapped_view
