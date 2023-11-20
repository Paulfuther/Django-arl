import json
import logging

from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import Group
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.edit import FormView

from arl.msg.helpers import client
from arl.tasks import (
    process_sendgrid_webhook,
    send_email_task,
    send_template_email_task,
)
from arl.user.models import CustomUser

from .forms import EmailForm, SMSForm, TemplateEmailForm

logger = logging.getLogger(__name__)


def is_member_of_msg_group(user):
    is_member = user.groups.filter(name="SendSMS").exists()
    if is_member:
        logger.info(f"{user} is a member of 'SendSMS' group.")
    else:
        logger.info(f"{user} is not a member of 'SendSMS' group.")
    return is_member


class SendSMSView(UserPassesTestMixin, FormView):
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
        selected_group = get_object_or_404(Group, pk=selected_group_id)

        # Retrieve users from the selected group
        selected_users = selected_group.user_set.filter(is_active=True)
        # Call the task to send sms.
        send_template_email_task(to_email, subject, name, template_id)

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Provide groups for form dropdown
        context["groups"] = Group.objects.all()
        return context


class SendTemplateEmailView(UserPassesTestMixin, FormView):
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


class SendEmailView(UserPassesTestMixin, FormView):
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


def fetch_twilio(request):
    sms = fetch_sms()
    truncated_sms = []
    for msg in sms:
        truncated_body = msg.body[:50]
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
    return render(request, "msg/sms_data.html", {"sms_data": truncated_sms})
