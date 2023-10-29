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

from arl.msg.helpers import create_tobacco_email, send_bulk_sms
from arl.tasks import send_email_task, send_sms_task, send_template_email_task
from arl.user.models import CustomUser

from .forms import EmailForm, SMSForm, TemplateEmailForm
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


@user_passes_test(is_member_of_msg_group)
def send_weekly_tobacco_emails(request):
    if request.method == "POST":
        active_users_with_email = CustomUser.objects.filter(
            Q(is_active=True) & ~Q(email="") & Q(email__isnull=False)
        )
        # users = CustomUser.objects.filter(is_active=True)  # Retrieve active users, adjust this as needed
        for user in active_users_with_email:
            to_email = user.email
            subject = "Required Actions for Tobacco and Vape"
            name = user.username
            template_id = "d-488749fd81d4414ca7bbb2eea2b830db"
            # Send the email to the current user
            create_tobacco_email(to_email, subject, name, template_id)

        return render(
            request, "msg/tobacco_success.html"
        )  # Show a success page or redirect as needed

    return render(request, "msg/send_tobacco_emails.html")


@user_passes_test(is_member_of_msg_group)
def send_weekly_tobacco_text(request):
    if request.method == "POST":
        # users = CustomUser.objects.filter(is_active=True)  # Retrieve active users, adjust this as needed
        active_users_with_phone = CustomUser.objects.filter(
            Q(is_active=True) & ~Q(phone_number="") & Q(phone_number__isnull=False)
        )
        # gsa returns an object. Although we can serialise the object, we still
        # have issues generating the proper format for twilio rest api.
        # so we do it old school.

        numbers = []
        for id in active_users_with_phone:
            gsatt = id.phone_number
            print(gsatt, id.username)
            numbers.append(gsatt)

        message = (
            "Required Action Policy for Tobacco and Vape Products WHAT IS REQUIRED? You must request ID from anyone purchasing tobacco or vape products, who looks to be younger than 40. WHY? It is against the law to sell tobacco or vape products to minors. A person who distributes tobacco or vape products to a minor is guilty of an offence, and could be punished with: Loss of employment. Face personal fines of $4,000 to $100,000. Loss of license to sell tobacco and vape products, as well as face additional fines of $10,000 to $150,000. (for the Associate) WHO? Each and every Guest that wants to buy tobacco products. REQUIRED Guests that look under the age of 40 are asked for (picture) I.D. when purchasing tobacco products. Ask for (picture) I.D. if they look under 40 before quoting the price of tobacco products. Ask for (picture) I.D. if they look under 40 before placing tobacco products on the counter. Dont let an angry Guest stop you from asking for (picture) I.D. ITs THE LAW! I.D. Drivers license Passport Certificate of Canadian Citizenship Canadian permanent resident card Canadian Armed Forces I.D. card Any documents issued by a federal or provincial authority or a foreign government that contain a photo, date of birth and signature are also acceptable. IMPORTANT - School I.D. cannot be accepted as proof of age. EXPECTED RESULTS. No employee is charged with selling tobacco products to a minor. Employees always remember to ask for I.D. No Employee receives a warning letter about selling to a minor.",
        )
        send_bulk_sms(numbers, message)

        return render(
            request, "msg/tobacco_sms_success.html"
        )  # Show a success page or redirect as needed

    return render(request, "msg/send_tobacco_sms.html")
