import json
import logging

from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.edit import FormView

from arl.tasks import (
    process_sendgrid_webhook,
    send_email_task,
    send_sms_task,
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_users'] = CustomUser.objects.filter(is_active=True)
        return context

    def form_valid(self, form):
        selected_users = form.cleaned_data["selected_users"]
        message = form.cleaned_data["message"]
        
        # Call the send_sms_task asynchronously for selected users
        for user in selected_users:
            #send_sms_task.delay(user.phone_number, message)
            print(user.phone_number, user.username)

        return super().form_valid(form)

class SendTemplateEmailView(UserPassesTestMixin, FormView):
    form_class = TemplateEmailForm
    template_name = "msg/template_email_form.html"
    success_url = reverse_lazy("sms_success")  # URL name for success page

    def test_func(self):
        return is_member_of_msg_group(self.request.user)

    def form_valid(self, form):
        to_email = form.cleaned_data["to_email"]
        subject = form.cleaned_data["subject"]
        name = form.cleaned_data["name"]
        template_id = form.cleaned_data["template_id"]
        send_template_email_task.delay(to_email, subject, name, template_id)
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
