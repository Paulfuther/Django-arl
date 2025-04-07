import logging
import traceback

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import FormView
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt

from arl.msg.helpers import send_bulk_sms
from arl.user.models import ErrorLog
from arl.user.tasks import send_payment_email_task

from .forms import EmployerRegistrationForm
from .models import EmployerRequest
from .tasks import post_stripe_payment_setup

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
            status=500,
        )


@csrf_exempt
def stripe_webhook(request):
    logger.info("✅ Stripe webhook endpoint called")
    payload = request.body
    sig_header = request.headers.get("Stripe-Signature", "")
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        logger.info(f"🧪 Stripe event type received: {event['type']}")
    except ValueError as e:
        logger.warning(f"❌ Invalid Stripe payload: {str(e)}")
        return JsonResponse({"error": "Invalid payload"}, status=400)
    except stripe.error.SignatureVerificationError as e:
        logger.warning(f"❌ Invalid Stripe signature: {str(e)}")
        return JsonResponse({"error": "Invalid signature"}, status=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_email") or session.get(
            "customer_details", {}
        ).get("email")

        logger.info(f"📦 Stripe webhook received: {event['type']}")
        logger.info(f"📧 Customer Email: {customer_email}")

        if not customer_email:
            logger.warning("⚠️ No customer email found in webhook session object.")
            return JsonResponse(
                {"status": "ignored", "reason": "No customer email"}, status=200
            )

        employer_request = EmployerRequest.objects.filter(email=customer_email).first()

        if employer_request:
            logger.info(
                f"🚀 Triggering post_stripe_payment_setup for EmployerRequest ID {employer_request.id}"
            )
            post_stripe_payment_setup.delay(
                employer_request.id,
                session_id=session.get("id"),
                subscription_id=session.get("subscription"),
                customer_id=session.get("customer"),
            )
        else:
            logger.warning(f"⚠️ No EmployerRequest found for email: {customer_email}")

    return JsonResponse({"status": "success"}, status=200)


def payment_success(request):
    return render(request, "setup/payment_success.html")


def payment_cancel(request):
    return render(request, "setup/payment_cancel.html")


@login_required
def approve_employer(request, pk):
    employer_request = get_object_or_404(EmployerRequest, pk=pk)

    if employer_request.status != "pending":
        messages.warning(request, "This request has already been processed.")
        return redirect("/admin/setup/employerrequest/")

    # ✅ Check if email is already in use
    User = get_user_model()
    if User.objects.filter(email__iexact=employer_request.email).exists():
        messages.error(request, "A user with this email already exists.")
        return redirect("/admin/setup/employerrequest/")

    # ✅ Validate Stripe plan
    stripe_plan = employer_request.stripe_plan
    if not stripe_plan or not stripe_plan.stripe_price_id:
        ErrorLog.objects.create(
            path=request.path,
            method=request.method,
            status_code=500,
            error_message=f"Stripe plan is not set for EmployerRequest {employer_request.id}",
        )
        messages.error(
            request, "Stripe plan is not selected for this employer request."
        )
        return redirect("/admin/setup/employerrequest/")

    # ✅ Create Stripe checkout session
    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            customer_email=employer_request.email,
            line_items=[{"price": stripe_plan.stripe_price_id, "quantity": 1}],
            success_url=f"{settings.BASE_URL}/payment-success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.BASE_URL}/payment-cancel",
        )
    except Exception as e:
        ErrorLog.objects.create(
            path=request.path,
            method=request.method,
            status_code=500,
            error_message=f"Stripe error: {str(e)}",
        )
        messages.error(request, "There was a problem creating the payment session.")
        return redirect("/admin/setup/employerrequest/")

    # ✅ Send email with payment link
    try:
        send_payment_email_task.delay(
            employer_request.email, checkout_session.url, employer_request.company_name
        )
    except Exception as e:
        ErrorLog.objects.create(
            path=request.path,
            method=request.method,
            status_code=500,
            error_message=f"Email send failed: {str(e)}",
        )
        messages.error(request, "Failed to send email with payment link.")
        return redirect("/admin/setup/employerrequest/")

    # ✅ Mark request as approved (we’ll use this in the webhook)
    employer_request.status = "approved"
    employer_request.save()

    messages.success(
        request, f"Payment link sent to {employer_request.email}. Awaiting completion."
    )
    return redirect("/admin/setup/employerrequest/")


class EmployerRegistrationView(FormView):
    template_name = "user/employer_registration.html"
    form_class = EmployerRegistrationForm
    success_url = reverse_lazy("employer_registration_success")

    def form_valid(self, form):
        employer_request = form.save(commit=False)
        employer_request.status = "pending"  # Mark as pending
        employer_request.save()

        requester_name = employer_request.company_name
        requester_email = employer_request.email
        sms_body = (
            f"🚨 New Employer Access Request: {requester_name} ({requester_email})"
        )

        try:
            send_bulk_sms(
                numbers=[+15196707469],  # Replace with your number
                body=sms_body,
                twilio_account_sid=settings.TWILIO_ACCOUNT_SID,
                twilio_auth_token=settings.TWILIO_AUTH_TOKEN,
                twilio_notify_sid=settings.TWILIO_NOTIFY_SERVICE_SID,
            )
            employer_request.save()

        except Exception as e:
            # ❌ Optionally, log or alert
            print(f"SMS Error: {e}")
            messages.error(
                self.request,
                "There was a problem submitting your request. Please try again.",
            )
            return self.form_invalid(form)  # 👈 Rerender the form

        # messages.success(self.request, "Your request has been submitted for review.")
        return super().form_valid(form)
