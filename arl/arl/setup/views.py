import logging
import traceback
from django.http import JsonResponse
from django.conf import settings
from arl.user.models import Employer, NewHireInvite
from arl.msg.helpers import create_master_email
from django.views.decorators.csrf import csrf_exempt
import stripe
from django.shortcuts import render
from django.utils.crypto import get_random_string

logger = logging.getLogger("django")


def trigger_error(request):
    """Triggers an internal server error (500) and logs full details without duplicate tracebacks."""
    try:
        raise ValueError("This is a test 500 internal server error.")
    except Exception as e:
        error_traceback = traceback.format_exc()  # ✅ Explicitly capture full traceback

        # ✅ Log the error once with full traceback
        logger.error(
            f"🚨 Internal Server Error at {request.path}\n"
            f"Error: {str(e)}\nTraceback:\n{error_traceback}",
            exc_info=False,  # 🚀 Prevents Django from adding duplicate traceback
        )

        # Return a structured 500 response
        return JsonResponse(
            {"error": "An unexpected error occurred. Check logs for details."},
            status=500
        )


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.headers.get("Stripe-Signature", "")
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return JsonResponse({"error": "Invalid payload"}, status=400)
    except stripe.error.SignatureVerificationError:
        return JsonResponse({"error": "Invalid signature"}, status=400)

    # ✅ Handle checkout completion
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        # 🔹 Extract email properly
        customer_email = session.get("customer_email")  # First attempt

        if not customer_email:
            customer_email = session.get("customer_details", {}).get("email")  # Second attempt

        print("Received Stripe webhook:", event["type"])
        print("Customer Email:", customer_email)

        # 🔹 If email is still None, log and return early
        if not customer_email:
            print("⚠️ No customer email found in webhook event. Skipping employer activation.")
            return JsonResponse({"status": "ignored", "reason": "No customer email"}, status=200)

        # ✅ Find the employer by email
        employer = Employer.objects.filter(email=customer_email).first()

        if employer:
            print(f"✅ Activating employer: {employer.name} ({employer.email})")
            employer.is_active = True
            employer.subscription_id = session.get("subscription")  # Store subscription ID if available
            employer.save()
            

            # ✅ Check if an invite already exists
            existing_invite = NewHireInvite.objects.filter(email=customer_email, used=False).first()
            if not existing_invite:
                # 🔹 Create a unique invite token
                invite_token = get_random_string(64)
                invite = NewHireInvite.objects.create(
                    employer=employer,
                    email=customer_email,
                    name=employer.name,
                    role="EMPLOYER",
                    token=invite_token
                )

                print(f"📩 Invite Created! Use this link: /register/{invite.token}/")


            # ✅ Send email using SendGrid template
            sendgrid_template_id = settings.SENDGRID_EMPLOYER_REGISTER_AS_USER
            # ✅ Generate an invite link for the employer
            invite_link = f"{settings.SITE_URL}/register/employer/"  # Ensure this URL is correct
            email_data = {
                "to_email": employer.email,
                "sendgrid_id": sendgrid_template_id,
                "template_data": {
                    "employer_name": employer.name,
                    "invite_link": invite_link,
                    "sender_contact_name": "Support Team",
                },
                "verified_sender": employer.verified_sender_email,
            }

            create_master_email(**email_data)  # ✅ Send email using helper function
            print(f"✅ Employer registration email sent to {employer.email}")

        else:
            print(f"⚠️ No employer found with email: {customer_email}")

    return JsonResponse({"status": "success"}, status=200)


def payment_success(request):
    return render(request, "setup/payment_success.html")


def payment_cancel(request):
    return render(request, "setup/payment_cancel.html")