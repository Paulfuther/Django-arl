import json
import logging

from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.edit import FormView

from arl.tasks import send_sms_task, send_template_email_task
from arl.user.models import CustomUser

from .forms import SMSForm, TemplateEmailForm
from .models import EmailEvent

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
        phone_number = form.cleaned_data["phone_number"]
        message = form.cleaned_data["message"]
        # Call the send_sms_task asynchronously
        send_sms_task.delay(phone_number, message)
        return super().form_valid(form)

class SendTemplateEmailView( FormView):
    form_class = TemplateEmailForm
    template_name = "msg/template_email_form.html"
    success_url = reverse_lazy("sms_success")  # URL name for success page

    #def test_func(self):
    #    return is_member_of_msg_group(self.request.user)

    def form_valid(self, form):
        to_email = form.cleaned_data['to_email']
        subject = form.cleaned_data['subject']
        name = form.cleaned_data['name']
        template_id = form.cleaned_data['template_id']
        send_template_email_task.delay(to_email, subject, name, template_id)
        return super().form_valid(form)


@csrf_exempt  # In production, use proper CSRF protection.
def sendgrid_webhook(request):
    if request.method == "POST":
        try:
            payload = json.loads(request.body.decode("utf-8"))
            if isinstance(payload, list) and len(payload) > 0:
                # Extract the first (and only) item from the list
                event_data = payload[0]
                email = event_data.get("email", "")
                event = event_data.get("event", "")
                ip = event_data.get("ip", "")
                sg_event_id = event_data.get("sg_event_id", "")
                sg_message_id = event_data.get("sg_message_id", "")
                sg_template_id = event_data.get("sg_template_id", "")
                sg_template_name = event_data.get("sg_template_name", "")
                timestamp = timezone.datetime.fromtimestamp(
                    event_data.get("timestamp", 0), tz=timezone.utc
                )
                url = event_data.get("url", "")
                useragent = event_data.get("useragent", "")

                # Find the user by email address in your custom user model
                try:
                    user = CustomUser.objects.get(email=email)
                except CustomUser.DoesNotExist:
                    user = None

                username = user.username if user else None

                # Create and save the EmailEvent instance
                event = EmailEvent(
                    email=email,
                    event=event,
                    ip=ip,
                    sg_event_id=sg_event_id,
                    sg_message_id=sg_message_id,
                    sg_template_id=sg_template_id,
                    sg_template_name=sg_template_name,
                    timestamp=timestamp,
                    url=url,
                    user=user,  # Set the user associated with this email event
                    username=username,
                    useragent=useragent,
                )
                event.save()

                return JsonResponse({"message": "Webhook received successfully"}, status=200)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON payload"}, status=400)
    else:
        return JsonResponse({"error": "Only POST requests are allowed"}, status=405)


def sms_success_view(request):
    return render(request, "msg/sms_success.html")
