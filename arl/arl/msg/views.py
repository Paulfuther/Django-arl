import json
import logging
import urllib.parse
from django.http import JsonResponse
from django.contrib.auth import get_user_model

from django.db.models import Q
from celery.result import AsyncResult
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import Group
from django.forms import modelformset_factory
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from django.views.generic.edit import FormView
from waffle.decorators import waffle_flag
from .models import ComplianceFile
from arl.dsign.forms import NameEmailForm
from arl.dsign.tasks import create_docusign_envelope_task
from arl.msg.helpers import (
    client,
    collect_attachments,
    custom_permission_denied,
    get_all_contact_lists,
    is_member_of_comms_group,
    is_member_of_docusign_group,
    is_member_of_email_group,
    is_member_of_msg_group,
    prepare_recipient_data,
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
    QuickEmailForm,
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
User = get_user_model()


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
    task = fetch_twilio_sms_task.delay(request.user.id)
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


@login_required
@user_passes_test(is_member_of_comms_group)
def communications(request):
    user = request.user
    active_tab = request.GET.get("tab", "email")
    print(user, active_tab)

    # Determine what tabs the user has access to
    valid_tabs = []
    if is_member_of_email_group(user):
        valid_tabs.append("email")
        valid_tabs.append("quick_email")
    if is_member_of_msg_group(user):
        valid_tabs.append("sms")
    if is_member_of_docusign_group(user):
        valid_tabs.append("docusign")

    # If they try to access a tab they don't have permission for, redirect to the first valid tab
    if active_tab not in valid_tabs:
        active_tab = valid_tabs[0] if valid_tabs else None

    # Default forms
    sms_form = SMSForm(user=user)
    email_form = TemplateEmailForm(user=user)
    quick_email_form = QuickEmailForm(user=user)
    docusign_form = NameEmailForm(user=user)

    if request.method == "POST":
        form_type = request.POST.get("form_type")

        if form_type == "quick_email":
            active_tab = "quick_email"
            quick_email_form = QuickEmailForm(request.POST, request.FILES, user=user)

            if quick_email_form.is_valid():
                subject = quick_email_form.cleaned_data["subject"]
                message = quick_email_form.cleaned_data["message"]
                selected_group = quick_email_form.cleaned_data["selected_group"]
                selected_users = quick_email_form.cleaned_data["selected_users"]

                employer = user.employer
                
                attachments = collect_attachments(request)

                if request.FILES.getlist("attachments") and attachments is None:
                    # User tried to upload but failed validation
                    return redirect("/comms/?tab=quick_email") 

                recipients = prepare_recipient_data(
                    user, selected_group, selected_users
                )

                # ✅ Now send using your new master helper (we'll have to create a basic helper)
                master_email_send_task.delay(
                    recipients=recipients,
                    sendgrid_id="d-4ac0497efd864e29b4471754a9c836eb",
                    attachments=attachments,
                    employer_id=request.user.employer.id,
                    body=message,
                    subject=subject
                )

                messages.success(request, "Quick email has been queued for delivery.")
                return redirect("/comms/?tab=quick_email")
            else:
                messages.error(request, "Please correct the errors below.")

        elif form_type == "email":
            active_tab = "email"
            if not is_member_of_email_group(user):
                return custom_permission_denied(
                    request, "You do not have permission to send email."
                )

            email_form = TemplateEmailForm(request.POST, request.FILES, user=user)

            if email_form.is_valid():
                sendgrid_template = email_form.cleaned_data.get("sendgrid_id")
                if not sendgrid_template:
                    messages.error(request, "No email template selected.")
                    return redirect("/comms/?tab=email")

                sendgrid_id = sendgrid_template.sendgrid_id
                selected_group = email_form.cleaned_data.get("selected_group")
                selected_users = email_form.cleaned_data.get("selected_users")
                employer = user.employer
                attachments = collect_attachments(request)
              
                if request.FILES.getlist("attachments") and attachments is None:
                    # User tried to upload but failed validation
                    return redirect("/comms/?tab=email")

                recipients = prepare_recipient_data(
                    user, selected_group, selected_users
                )

                master_email_send_task.delay(
                    recipients=recipients,
                    sendgrid_id=sendgrid_id,
                    attachments=attachments,
                    employer_id=employer.id if employer else None,
                )

                messages.success(request, "Emails have been queued for delivery.")
                return redirect("/comms/?tab=email")
            else:
                messages.error(request, "Please correct the errors below.")
                
        elif form_type == "sms":
            active_tab = "sms"
            if not is_member_of_msg_group(user):
                return custom_permission_denied(
                    request, "You do not have permission to send text messages."
                )

            sms_form = SMSForm(request.POST, user=user)

            if sms_form.is_valid():
                group = sms_form.cleaned_data["selected_group"]
                sms_message = sms_form.cleaned_data["message"]

                send_one_off_bulk_sms_task.delay(group.id, sms_message, user.id)
                messages.success(request, "SMS is being sent.")
                return redirect("/comms/?tab=sms")

        elif form_type == "docusign":
            active_tab = "docusign"
            if not is_member_of_docusign_group(user):
                return custom_permission_denied(
                    request, "You do not have permission to send DocuSign documents."
                )

            docusign_form = NameEmailForm(request.POST, user=user)

            if docusign_form.is_valid():
                recipient = docusign_form.cleaned_data["recipient"]
                ds_template = docusign_form.cleaned_data["template_id"]
                template = docusign_form.cleaned_data["template_name"]
                template_name = (
                    template.template_name if template else "Unknown Template"
                )

                envelope_args = {
                    "signer_email": recipient.email,
                    "signer_name": recipient.get_full_name(),
                    "template_id": ds_template,
                }

                logger.info(f"Sending DocuSign envelope: {envelope_args}")

                create_docusign_envelope_task.delay(envelope_args)

                messages.success(
                    request,
                    f"Thank you. The document '{template_name}' has been sent to {recipient.get_full_name()}.",
                )
                return redirect("/comms/?tab=docusign")

            messages.error(request, "Please correct the DocuSign form.")
            
    selected_ids = request.POST.getlist("selected_users") if request.method == "POST" else []
    return render(
        request,
        "msg/master_comms.html",
        {
            "email_form": email_form,
            "quick_email_form": quick_email_form,
            "sms_form": sms_form,
            "docusign_form": docusign_form,
            "active_tab": active_tab,
            "can_send_email": is_member_of_email_group(user),
            "can_send_sms": is_member_of_msg_group(user),
            "can_send_docusign": is_member_of_docusign_group(user),
            "selected_ids": selected_ids,
        },
    )


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
    form = TemplateFilterForm(request.GET or None, user=request.user)
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


@login_required
def search_users_view(request):
    query = request.GET.get("search", "")
    employer = request.user.employer

    users = User.objects.filter(employer=employer, is_active=True).order_by("last_name", "first_name")
    if query:
        users = users.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        )

    selected_ids = request.GET.getlist("selected_users")

    return render(request, "msg/partials/user_checkboxes.html", {
        "users": users,
        "selected_ids": selected_ids
    })


# View for weekly compliance notes
def latest_compliance_file(request):
    file = ComplianceFile.objects.filter(is_active=True).first()
    if file:
        return redirect(file.file.url)
    return redirect("/")  # fallback