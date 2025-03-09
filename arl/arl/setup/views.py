import logging
import traceback
from django.http import JsonResponse
from django.conf import settings
from arl.user.models import Employer
from django.views.decorators.csrf import csrf_exempt
import stripe
from django.shortcuts import render

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
        else:
            print(f"⚠️ No employer found with email: {customer_email}")

    return JsonResponse({"status": "success"}, status=200)


def payment_success(request):
    return render(request, "setup/payment_success.html")


def payment_cancel(request):
    return render(request, "setup/payment_cancel.html")