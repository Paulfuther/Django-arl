import json
import logging

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import Group
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from django.views.generic.edit import FormView
from waffle.decorators import waffle_flag
from waffle.mixins import WaffleFlagMixin

from arl.msg.helpers import client
from arl.tasks import (
    process_sendgrid_webhook,
    send_email_task,
    send_one_off_bulk_sms_task,
    send_template_email_task,
)
from arl.user.models import CustomUser, Store

from .forms import EmailForm, SMSForm, TemplateEmailForm

logger = logging.getLogger(__name__)


def is_member_of_msg_group(user):
    is_member = user.groups.filter(name="SendSMS").exists()
    if is_member:
        logger.info(f"{user} is a member of 'SendSMS' group.")
    else:
        logger.info(f"{user} is not a member of 'SendSMS' group.")
    return is_member


class SendSMSView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    form_class = SMSForm
    template_name = "msg/sms_form.html"
    success_url = reverse_lazy("sms_success")  # URL name for success page

    def test_func(self):
        return is_member_of_msg_group(self.request.user)

    def form_valid(self, form):
        # Fetch the ID
        selected_group_id = form.cleaned_data["selected_group"].id
        message = form.cleaned_data["message"]

        # Retrieve the selected group using its ID
        group = get_object_or_404(Group, pk=selected_group_id)
        group_id = group.id

        # Call the task to send sms.
        send_one_off_bulk_sms_task.delay(group_id, message)

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Provide groups for form dropdown
        context["groups"] = Group.objects.all()
        return context


class SendTemplateEmailView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    form_class = TemplateEmailForm
    template_name = "msg/template_email_form.html"
    # URL name for success page
    success_url = reverse_lazy("template_email_success")

    def test_func(self):
        return is_member_of_msg_group(self.request.user)

    def form_valid(self, form):
        subject = form.cleaned_data["subject"]
        selected_group_id = form.cleaned_data["selected_group"].id
        sendgrid_template = form.cleaned_data["sendgrid_id"]

        # Fetch the group and sendgrid_id
        group = get_object_or_404(Group, pk=selected_group_id)
        group_id = group.id
        sendgrid_id = (
            sendgrid_template.sendgrid_id
        )  # Assuming sendgrid_id is a field in the EmailTemplate model

        # Now you have both the group_id and the corresponding sendgrid_id
        # Use these to send emails to the entire group
        send_template_email_task.delay(group_id, subject, sendgrid_id)

        return super().form_valid(form)


class SendEmailView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    form_class = EmailForm
    template_name = "msg/email_form.html"
    success_url = reverse_lazy("sms_success")  # URL name for success page

    def test_func(self):
        return is_member_of_msg_group(self.request.user)

    def form_valid(self, form):
        to_email = form.cleaned_data["to_email"]
        subject = form.cleaned_data["subject"]
        body = form.cleaned_data["body"]
        send_email_task.delay(to_email, subject, body)
        return super().form_valid(form)


@csrf_exempt  # In production, use proper CSRF protection.
def sendgrid_webhook(request):
    if request.method == "POST":
        try:
            payload = json.loads(request.body.decode("utf-8"))
            process_sendgrid_webhook.delay(payload)
            return JsonResponse(
                {"message": "Webhook received successfully"}, status=200
            )
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON payload"}, status=400)
    else:
        return JsonResponse({"error": "Only POST requests are allowed"}, status=405)


def sms_success_view(request):
    return render(request, "msg/sms_success.html")


def template_email_success_view(request):
    return render(request, "msg/template_email_success.html")


def fetch_sms():
    return client.messages.list(limit=200)


class FetchTwilioView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "msg/sms_data.html"

    def test_func(self):
        return is_member_of_msg_group(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sms = fetch_sms()
        truncated_sms = []
        for msg in sms:
            truncated_body = msg.body[:250]
            # Fetch user data based on the phone number
            user = CustomUser.objects.filter(phone_number=msg.to).first()
            username = f"{user.first_name} {user.last_name}" if user else None
            # if user exists
            msg_data = {
                "sid": msg.sid,
                "date_sent": msg.date_sent,
                "from": msg.from_,
                "to": msg.to,
                "body": truncated_body,
                "username": username,  # Add the username to the SMS data
                # Add more fields as needed
            }
            truncated_sms.append(msg_data)
        context["sms_data"] = truncated_sms
        return context


def fetch_calls():
    return client.calls.list(limit=20)


class FetchTwilioCallsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "msg/call_data.html"

    def test_func(self):
        return is_member_of_msg_group(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        calls = fetch_calls()
        if calls is None:
            # Set an error message in the context
            context["error_message"] = (
                "Failed to fetch call logs. Please try again later."
            )
            return context

        truncated_calls = []
        for call in calls:
            twilio_to_number = str(call.to)
            store = Store.objects.filter(phone_number=str(twilio_to_number)).first()
            store_phone_number = (
                str(store.phone_number) if store and store.phone_number else None
            )
            store_number = store.number if store and store.number else None
            call_data = {
                "date_created": call.date_created,
                "to": twilio_to_number,
                "duration": call.duration,
                "store_phone_number": (
                    store_phone_number if store_phone_number else "Unknown Phone Number"
                ),
                "store_number": (
                    store_number if store_number else "Unknown Store Number"
                ),
                # Add more fields as needed
            }
            truncated_calls.append(call_data)

        context["call_data"] = truncated_calls
        return context


def comms(request):
    return render(request, "msg/master_comms.html")


@waffle_flag("email_api")
def EmailEventList(request):
    return HttpResponse("This view is controlled by a feature flag.")


def click_thank_you(request):
    return render(request, "msg/thank_you.html")
