import base64
import json
import logging
import urllib.parse

from celery.result import AsyncResult
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import Group
from django.forms import modelformset_factory
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from django.views.generic.edit import FormView
from waffle.decorators import waffle_flag

from arl.msg.helpers import (
    client,
    get_all_contact_lists,
    send_whats_app_carwash_sites_template,
)
from arl.msg.tasks import (
    process_whatsapp_webhook,
    send_template_whatsapp_task,
    start_campaign_task,
)
from arl.user.models import CustomUser, Store

from .forms import (
    CampaignSetupForm,
    EmployeeSearchForm,
    GroupSelectForm,
    SendGridFilterForm,
    SMSForm,
    StoreTargetForm,
    TemplateEmailForm,
    TemplateFilterForm,
    TemplateWhatsAppForm,
)
from .tasks import (
    fetch_twilio_sms_task,
    fetch_twilio_summary,
    filter_sendgrid_events,
    generate_email_event_summary,
    generate_employee_email_report_task,
    master_email_send_task,
    process_sendgrid_webhook,
    send_one_off_bulk_sms_task,
)

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

    def get_form_kwargs(self):
        """Pass the logged-in user to the form to ensure we know their employer."""
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user  # ✅ Pass the current user
        return kwargs

    def form_valid(self, form):
        selected_group = form.cleaned_data["selected_group"]
        message = form.cleaned_data["message"]
        user_id = self.request.user.id

        # ✅ Pass only valid numbers to the SMS task
        send_one_off_bulk_sms_task.delay(selected_group.id, message, user_id)

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        """Filter groups by employer and pass them to the context."""
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user and user.employer:
            employer = user.employer
            groups = Group.objects.filter(user__employer=employer).distinct()
        else:
            groups = Group.objects.none()  # No groups if no employer is found

        context["groups"] = groups  # ✅ Pass filtered groups
        return context


class SendTemplateEmailView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    form_class = TemplateEmailForm
    template_name = "msg/template_email_form.html"
    success_url = reverse_lazy("template_email_success")

    def get_form_kwargs(self):
        """Pass the current user to the form dynamically."""
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user  # ✅ Pass user here
        return kwargs

    def test_func(self):
        return is_member_of_msg_group(self.request.user)

    def form_valid(self, form):
        # Retrieve the template ID and fetch the corresponding instance
        sendgrid_template = form.cleaned_data.get("sendgrid_id").first()
        print(sendgrid_template.id)
        if not sendgrid_template:
            return JsonResponse(
                {"success": False, "error": "No email template selected."}, status=400
            )
        # Use the SendGrid ID directly
        sendgrid_id = sendgrid_template.sendgrid_id
        selected_groups = form.cleaned_data.get("selected_group")
        selected_users = form.cleaned_data.get("selected_users")

        if not selected_groups and not selected_users:
            return JsonResponse(
                {"success": False, "error": "No recipients selected."}, status=400
            )
        employer = self.request.user.employer

        # Collect attachments
        attachments = self.collect_attachments()
        if attachments is None:
            return JsonResponse(
                {
                    "success": False,
                    "error": "One or more attachments exceed the 10MB size limit.",
                },
                status=400,
            )

        # Gather recipient data
        recipients = self.prepare_recipient_data(selected_groups, selected_users)

        # Debugging: Log recipient data
        print("Prepared recipient data:", recipients, sendgrid_id)

        # Pass data to the task
        master_email_send_task.delay(
            recipients=recipients,
            sendgrid_id=sendgrid_id,
            attachments=attachments,
            employer_id=employer.id if employer else None,
        )

        print("sent")
        if self.request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "success": True,
                    "message": "Emails processed! Refresh after closing this message.",
                }
            )

        return super().form_valid(form)

    def form_invalid(self, form):
        print("Form validation failed. Errors:", form.errors)

        if self.request.headers.get("x-requested-with") == "XMLHttpRequest":
            # Render the form with errors as HTML
            html = render_to_string(self.template_name, {"form": form}, self.request)
            return JsonResponse({"success": False, "html": html})

        return self.render_to_response(self.get_context_data(form=form))

    def collect_attachments(self):
        attachments = []
        for field_name in ["attachment_1", "attachment_2", "attachment_3"]:
            file = self.request.FILES.get(field_name)
            if file:
                # Validate file size (10 MB limit)
                if file.size > 10 * 1024 * 1024:
                    messages.error(
                        self.request, f"{file.name} exceeds the 10MB size limit."
                    )
                    return None

                # Serialize the attachment
                attachments.append(
                    {
                        "file_name": file.name,
                        "file_type": file.content_type,
                        "file_content": base64.b64encode(file.read()).decode("utf-8"),
                    }
                )
                print(file.name)
        return attachments

    def prepare_recipient_data(self, selected_groups, selected_users):
        """
        Gather user names and email addresses from selected groups and users.
        """
        recipients = []  # Use a list to store dictionaries with name and email
        employer = self.request.user.employer

        if selected_groups:
            for group in selected_groups:
                for user in group.user_set.filter(is_active=True, employer=employer):
                    recipients.append(
                        {
                            "name": user.get_full_name(),
                            "email": user.email,
                            "status": "Active",
                        }
                    )

        if selected_users:
            for user in selected_users:
                recipients.append(
                    {
                        "name": user.get_full_name(),
                        "email": user.email,
                        "status": "Active",
                    }
                )

        # Remove duplicates based on email
        unique_recipients = {
            recipient["email"]: recipient for recipient in recipients
        }.values()
        # Debugging: Print recipient data
        for recipient in unique_recipients:
            print(recipient["email"], recipient["status"])
        return list(unique_recipients)


class SendTemplateWhatsAppView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    form_class = TemplateWhatsAppForm
    template_name = "msg/whatsapp_form.html"
    # URL name for success page
    success_url = reverse_lazy("template_whats_app_success")

    def test_func(self):
        return is_member_of_msg_group(self.request.user)

    def form_valid(self, form):
        selected_group_id = form.cleaned_data["selected_group"].id
        whatsapp_template = form.cleaned_data["whatsapp_id"]
        from_id = "MGb005e5fe6d147e13d0b2d1322e00b1cb"
        # Fetch the group and sendgrid_id
        group = get_object_or_404(Group, pk=selected_group_id)
        group_id = group.id
        whatsapp_id = (
            whatsapp_template.content_sid
        )  # Assuming sendgrid_id is a field in the EmailTemplate model

        # Now you have both the group_id and the corresponding sendgrid_id
        # Use these to send emails to the entire group
        print(group_id)
        send_template_whatsapp_task.delay(whatsapp_id, from_id, group_id)
        # print(group_id)
        return super().form_valid(form)


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
                "status": (call.status),
                # Add more fields as needed
            }
            truncated_calls.append(call_data)

        context["call_data"] = truncated_calls
        return context


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


def template_whats_app_success_view(request):
    return render(request, "msg/template_whats_app_success.html")


def fetch_sms():
    return client.messages.list(limit=1000)


# this is for whatas app.
def fetch_whatsapp_messages(account_sid, auth_token):
    # Fetch messages sent via WhatsApp
    messages = client.messages.list(limit=20)  # Adjust 'limit' as needed

    for message in messages:
        if "whatsapp:" in message.from_:  # Filter messages sent from a WhatsApp number
            print(
                f"From: {message.from_}, To: {message.to}, Body: {message.body}, Status: {message.status}, Date Sent: {message.date_sent}"
            )


def fetch_calls():
    return client.calls.list(limit=20)


def fetch_twilio_data(request):
    # Run the synchronous task
    task = fetch_twilio_summary.delay()
    return JsonResponse({"task_id": task.id})


def fetch_sms_data(request):
    task = fetch_twilio_sms_task.delay()
    return JsonResponse({"task_id": task.id})


def get_task_status(request, task_id):
    task = AsyncResult(task_id)
    if task.state == "SUCCESS":
        return JsonResponse({"status": "success", "result": task.result})
    elif task.state == "FAILURE":
        return JsonResponse({"status": "failure", "error": str(task.result)})
    else:
        return JsonResponse({"status": "pending"})


def message_summary_view(request):
    return render(request, "msg/message_summary.html")


# this is for the summary view
def sms_summary_view(request):
    return render(request, "msg/sms_data.html")


def comms(request):
    return render(request, "msg/master_comms.html")


@waffle_flag("email_api")
def EmailEventList(request):
    return HttpResponse("This view is controlled by a feature flag.")


def click_thank_you(request):
    return render(request, "msg/thank_you.html")


@csrf_exempt
def whatsapp_webhook(request):
    if request.method != "POST":
        return render(request, "incident/405.html", status=405)
    try:
        user = request.POST.get("From")
        message = request.POST.get("Body")
        print(f"{user} says {message}")
        body_unicode = request.body.decode("utf-8")
        data = urllib.parse.parse_qs(body_unicode)
        print(f"📩 Twilio Webhook Data: {json.dumps(data, indent=2)}")
        process_whatsapp_webhook.delay(data)
    except Exception as e:
        logger.error(f"Error processing webhook data: {e}")
        return JsonResponse(
            {"status": "error", "message": "Internal Server Error"}, status=500
        )

    return JsonResponse({"status": "success"}, status=200)


StoreFormSet = modelformset_factory(
    Store, form=StoreTargetForm, extra=0, fields=("number", "sales_target")
)


def carwash_targets(request):
    if request.method == "POST":
        print(request.POST)
        formset = StoreFormSet(request.POST)
        group_form = GroupSelectForm(request.POST)
        if formset.is_valid() and group_form.is_valid():
            formset.save()
            # Get the user name (assuming it's from request.user or another source)
            user_name = request.user.first_name  # Or however you get the user's name

            # Build content variables for the WhatsApp message
            content_vars = {"1": user_name}  # First placeholder is the user's name
            row_number = 2  # Start after 1 since 1 is used for the username
            # Extract store number and sales target from the cleaned data

            for form in formset:
                store_number = form.cleaned_data["number"]
                target = form.cleaned_data["sales_target"]
                content_vars[f"{row_number}"] = f"Store {store_number}"
                content_vars[f"{row_number + 1}"] = f"Target {target}"
                row_number += 2
            print("contentvars", content_vars)
            content_vars_json = json.dumps(content_vars)
            # Get the selected group
            selected_group = group_form.cleaned_data["group"]
            print("selected group", selected_group)
            group_id = selected_group.id
            print("group id", group_id)
            whatsapp_template = "HX1a363c5a2312c9baeb34daed5d422f9d"
            from_sid = "MGb005e5fe6d147e13d0b2d1322e00b1cb"
            whatsapp_id = whatsapp_template
            # Assuming sendgrid_id is a field in the EmailTemplate model
            group = Group.objects.get(pk=group_id)
            users_in_group = group.user_set.filter(is_active=True)
            for user in users_in_group:
                print(user.first_name, user.phone_number, content_vars)
                send_whats_app_carwash_sites_template(
                    whatsapp_id,
                    from_sid,
                    user.first_name,
                    user.phone_number,
                    content_vars_json,
                )
    else:
        # Filter the queryset to include only carwash stores
        queryset = Store.objects.filter(carwash=True)
        formset = StoreFormSet(queryset=queryset)
        group_form = GroupSelectForm()

    return render(
        request,
        "msg/carwash_targets.html",
        {"formset": formset, "group_form": group_form},
    )


def sendgrid_webhook_view(request):
    # Initialize form with GET data
    form = SendGridFilterForm(request.GET or None)

    # Initialize an empty list for event data
    events = []

    if form.is_valid() and form.cleaned_data.get("template_id"):
        date_from = form.cleaned_data["date_from"]
        date_to = form.cleaned_data["date_to"]
        template_id = form.cleaned_data["template_id"].sendgrid_id

        # Trigger the Celery task and get the result
        task = filter_sendgrid_events.delay(date_from, date_to, template_id)
        events = task.get()  # Wait for the task to complete and get the result

    return render(
        request,
        "msg/sendgrid_webhook_table.html",
        {
            "events": events,
            "form": form,
        },
    )


def email_event_summary_view(request):
    form = TemplateFilterForm(request.GET or None)
    summary_table = ""

    # Only proceed with task if form is valid and template_id is provided
    if form.is_valid() and form.cleaned_data.get("template_id"):
        template_id = form.cleaned_data["template_id"].sendgrid_id
        start_date = form.cleaned_data.get("start_date")
        end_date = form.cleaned_data.get("end_date")
        # Call the Celery task
        result = generate_email_event_summary.delay(template_id, start_date, end_date)
        summary_table = result.get(timeout=10)  # Wait for task completion

    return render(
        request,
        "msg/email_event_summary_table.html",
        {
            "summary_table": summary_table,
            "form": form,
        },
    )


def employee_email_report_view(request):
    form = EmployeeSearchForm(request.GET or None)
    report_table = None

    if form.is_valid():
        # Fetch the selected employee
        employee = form.cleaned_data.get("employee")
        if employee:
            # Trigger the Celery task with the employee ID
            result = generate_employee_email_report_task.delay(employee_id=employee.id)

            # Wait for the result (blocking, for demonstration purposes)
            report_table = result.get(timeout=10)
    # print(report_table)
    return render(
        request,
        "msg/employee_email_report.html",
        {
            "form": form,
            "report_table": report_table,
        },
    )


def campaign_setup_view(request):
    contact_lists = get_all_contact_lists()
    contact_list_choices = [(cl["id"], cl["name"]) for cl in contact_lists]

    if request.method == "POST":
        # Pass the dynamic choices to the form during POST
        form = CampaignSetupForm(request.POST)
        form.fields["contact_list"].choices = contact_list_choices

        if form.is_valid():
            selected_list_id = form.cleaned_data["contact_list"]
            try:
                # Sync contacts with the selected list and start the campaign
                start_campaign_task.delay(selected_list_id)

                messages.success(request, "Campaign started successfully!")
                return redirect("home")  # Redirect to a success page
            except Exception as e:
                messages.error(request, f"Error starting campaign: {e}")
    else:
        # Pass the choices to the form during GET
        form = CampaignSetupForm()
        form.fields["contact_list"].choices = contact_list_choices

    return render(request, "msg/campaign_setup.html", {"form": form})


def get_group_emails(request):
    if request.method == "GET":
        user = request.user
        employer = user.employer
        # Retrieve group IDs from the query parameters
        group_ids = request.GET.get("group_ids", "")  # Returns a string like "1,2,3"
        if not group_ids:
            return JsonResponse(
                {"emails": [], "error": "No group IDs provided."}, status=400
            )

        # Convert the string of IDs into a list of integers
        group_id_list = [
            int(group_id) for group_id in group_ids.split(",") if group_id.isdigit()
        ]

        # Query active users in the specified groups
        users = CustomUser.objects.filter(
            groups__id__in=group_id_list, is_active=True, employer=employer
        ).distinct()

        email_list = [{"email": user.email, "status": "Active"} for user in users]

        return JsonResponse({"emails": email_list}, status=200)
    return JsonResponse({"error": "Invalid request method."}, status=400)


def tobacco_vape_policy_view(request):
    """
    Render the Tobacco and Vape Products Required Action Policy.
    """
    return render(request, "msg/tobacco_vape_policy.html")
