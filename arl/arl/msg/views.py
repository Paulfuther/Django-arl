import json
import logging
import urllib.parse

import pandas as pd
from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import Group
from django.contrib.messages.views import SuccessMessageMixin
from django.forms import modelformset_factory
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from django.views.generic.edit import CreateView, FormView
from waffle.decorators import waffle_flag

from arl.msg.helpers import (client, get_all_contact_lists,
                             send_whats_app_carwash_sites_template)
from arl.msg.models import EmailTemplate
from arl.msg.tasks import (process_whatsapp_webhook,
                           send_template_whatsapp_task, start_campaign_task)
from arl.tasks import (send_email_task, send_one_off_bulk_sms_task,
                       send_template_email_task)
from arl.user.models import CustomUser, Store

from .forms import (CampaignSetupForm, SendGridFilterForm,
                    SMSForm, TemplateEmailForm, TemplateFilterForm,
                    TemplateWhatsAppForm)
from .tasks import (filter_sendgrid_events, generate_email_event_summary,
                    process_sendgrid_webhook)

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


class SendEmailView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return is_member_of_msg_group(self.request.user)

    def get(self, request, *args, **kwargs):
        # Fetch available groups and email templates
        groups = Group.objects.all()
        templates = EmailTemplate.objects.all()

        # Render the form with context
        return render(request, "msg/email_form.html", {"groups": groups, "templates": templates})

    def post(self, request, *args, **kwargs):
        try:
            # Retrieve form data
            selected_group_id = request.POST.get('selected_group')
            template_id = request.POST.get('template_id')

            # Validate required fields
            if not selected_group_id or not template_id:
                messages.error(request, "Group and Template are required.")
                return self.get(request)

            # Retrieve selected group and template
            selected_group = Group.objects.get(id=selected_group_id)
            email_template = EmailTemplate.objects.get(id=template_id)

            # Retrieve uploaded files
            uploaded_files = request.FILES.getlist('attachments')

            # Debugging: Log uploaded files
            print("Uploaded files:", uploaded_files)

            if not uploaded_files:
                messages.error(request, "No files were submitted. Please upload at least one file.")
                return self.get(request)

            # Validate file size
            for file in uploaded_files:
                if file.size > 10 * 1024 * 1024:  # 10 MB limit
                    messages.error(request, f"{file.name} exceeds the 10MB size limit.")
                    return self.get(request)

            # Prepare attachments
            attachments = []
            for file in uploaded_files:
                attachments.append({
                    'file_name': file.name,
                    'file_type': file.content_type,
                    'file_content': file.read()
                })

            # Debugging: Log attachments
            print("Attachments prepared:", attachments)

            # Call task to send emails
            send_email_task.delay(selected_group.id,
                                  email_template.sendgrid_id, attachments)

            messages.success(request, "Emails with attachments are being sent!")
            return redirect(reverse_lazy("template_email_success"))
        except Group.DoesNotExist:
            messages.error(request, "Selected group does not exist.")
        except EmailTemplate.DoesNotExist:
            messages.error(request, "Selected email template does not exist.")
        except Exception as e:
            # Handle other exceptions
            print("Error in SendEmailView:", str(e))
            messages.error(request, f"An error occurred: {str(e)}")

        # Render the form with errors
        return self.get(request)


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
                "price": msg.price,
                "price unit": msg.price_unit
            }
            truncated_sms.append(msg_data)
        context["sms_data"] = truncated_sms
        return context


def fetch_calls():
    return client.calls.list(limit=20)


class TwilioMessageSummary:
    def __init__(self, client):
        # Use the existing Twilio client
        self.client = client

    def fetch_messages(self, limit=1000):
        # Fetch the messages from Twilio
        messages = self.client.messages.list(limit=limit)
        return messages

    def separate_messages(self, messages):
        # Separate SMS and WhatsApp messages
        sms_data = []
        whatsapp_data = []

        for message in messages:
            if message.price:  # Ensure the message has pricing data
                data = {
                    'date_sent': message.date_sent,
                    'price': float(message.price),
                    'price_unit': message.price_unit,
                    'sid': message.sid
                }

                # Separate based on the 'from_' or 'to' fields containing 'whatsapp:'
                if 'whatsapp:' in message.from_ or 'whatsapp:' in message.to:
                    whatsapp_data.append(data)
                else:
                    sms_data.append(data)

        return sms_data, whatsapp_data

    def summarize_by_month(self, data):
        # Create a DataFrame from the data
        df = pd.DataFrame(data)

        if df.empty:
            return pd.DataFrame(columns=['date_sent', 'price'])  # Return empty DataFrame if no data

        # Convert 'date_sent' to a datetime type and remove timezone information
        df['date_sent'] = pd.to_datetime(df['date_sent']).dt.tz_localize(None)

        # Group by year and month, then sum the 'price' column
        summary = df.groupby(df['date_sent'].dt.to_period('M')).agg({
            'price': 'sum'
        }).reset_index()

        # Format the date as year-month
        summary['date_sent'] = summary['date_sent'].dt.strftime('%Y-%m')

        return summary.to_dict('records')  # Return as a list of dictionaries

    def get_sms_and_whatsapp_summary(self, limit=1000):
        # Fetch, separate, and summarize messages
        messages = self.fetch_messages(limit=limit)
        sms_data, whatsapp_data = self.separate_messages(messages)

        sms_summary = self.summarize_by_month(sms_data)
        whatsapp_summary = self.summarize_by_month(whatsapp_data)

        return sms_summary, whatsapp_summary


def message_summary_view(request):
    twilio_summary = TwilioMessageSummary(client)

    # Get the SMS and WhatsApp message summaries as lists of dictionaries
    sms_summary, whatsapp_summary = twilio_summary.get_sms_and_whatsapp_summary()

    # Pass the lists directly to the template
    context = {
        'sms_summary': sms_summary,
        'whatsapp_summary': whatsapp_summary,
    }

    return render(request, 'msg/message_summary.html', context)


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
                "status": (
                    call.status
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


@csrf_exempt
def whatsapp_webhook(request):
    if request.method != "POST":
        return render(request, "incident/405.html", status=405)
    try:
        user = request.POST.get('From')
        message = request.POST.get('Body')
        print(f'{user} says {message}')
        body_unicode = request.body.decode("utf-8")
        data = urllib.parse.parse_qs(body_unicode)
        process_whatsapp_webhook.delay(data)
    except Exception as e:
        logger.error(f"Error processing webhook data: {e}")
        return JsonResponse(
            {"status": "error", "message": "Internal Server Error"}, status=500
        )

    return JsonResponse({"status": "success"}, status=200)


class StoreTargetForm(forms.ModelForm):
    sales_target = forms.IntegerField(required=True, label='Sales Target')

    class Meta:
        model = Store
        fields = ['number', 'sales_target']

    def __init__(self, *args, **kwargs):
        super(StoreTargetForm, self).__init__(*args, **kwargs)
        self.fields['number'].disabled = True
        self.fields['number'].label = "Store Number"


StoreFormSet = modelformset_factory(Store, form=StoreTargetForm, extra=0, 
                                    fields=('number', 'sales_target'))


# Form for selecting a group
class GroupSelectForm(forms.Form):
    group = forms.ModelChoiceField(queryset=Group.objects.all(), required=True, label="Select Group")


def carwash_targets(request):
    if request.method == 'POST':
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
                store_number = form.cleaned_data['number']
                target = form.cleaned_data['sales_target']
                content_vars[f"{row_number}"] = f"Store {store_number}"
                content_vars[f"{row_number+1}"] = f"Target {target}"
                row_number += 2
            print("contentvars", content_vars)
            content_vars_json = json.dumps(content_vars)
            # Get the selected group
            selected_group = group_form.cleaned_data['group']
            print("selected group", selected_group)
            group_id = selected_group.id
            print("group id", group_id)
            whatsapp_template = "HX1a363c5a2312c9baeb34daed5d422f9d"
            from_sid = "MGb005e5fe6d147e13d0b2d1322e00b1cb"
            whatsapp_id = (whatsapp_template)
            # Assuming sendgrid_id is a field in the EmailTemplate model
            group = Group.objects.get(pk=group_id)
            users_in_group = group.user_set.filter(is_active=True)
            for user in users_in_group:
                print(user.first_name, user.phone_number, content_vars)
                send_whats_app_carwash_sites_template(whatsapp_id, from_sid,
                                                      user.first_name,
                                                      user.phone_number,
                                                      content_vars_json
                                                    )
    else:
        # Filter the queryset to include only carwash stores
        queryset = Store.objects.filter(carwash=True)
        formset = StoreFormSet(queryset=queryset)
        group_form = GroupSelectForm()

    return render(request, 'msg/carwash_targets.html', {'formset': formset, 'group_form': group_form})
   

class TwilioView(LoginRequiredMixin, UserPassesTestMixin, View):

    def test_func(self):
        return is_member_of_msg_group(self.request.user)

    def get(self, request, *args, **kwargs):
        # Check the requested URL path to determine the function to execute
        if request.path == '/messages/':
            return self.list_messages(request)
        elif request.path == '/message-summary/':
            return self.summarize_costs(request)

    def list_messages(self, request):
        sms = fetch_sms()
        truncated_sms = []
        for msg in sms:
            truncated_body = msg.body[:1000]
            user = CustomUser.objects.filter(phone_number=msg.to).first()
            username = f"{user.first_name} {user.last_name}" if user else None
            msg_data = {
                "sid": msg.sid,
                "date_sent": msg.date_sent,
                "from": msg.from_,
                "to": msg.to,
                "body": truncated_body,
                "username": username,
                "price": msg.price,
                "price_unit": msg.price_unit
            }
            truncated_sms.append(msg_data)
        context = {
            "sms_data": truncated_sms
        }
        return render(request, "msg/sms_data.html", context)

    def summarize_costs(self, request):
        twilio_summary = TwilioMessageSummary(client)
        sms_summary, whatsapp_summary = twilio_summary.get_sms_and_whatsapp_summary()
        context = {
            'sms_summary': sms_summary,
            'whatsapp_summary': whatsapp_summary,
        }
        return render(request, 'msg/message_summary.html', context)


def sendgrid_webhook_view(request):
    # Initialize form with GET data
    form = SendGridFilterForm(request.GET or None)

    # Initialize an empty list for event data
    events = []

    if form.is_valid() and form.cleaned_data.get('template_id'):
        date_from = form.cleaned_data['date_from']
        date_to = form.cleaned_data['date_to']
        template_id = form.cleaned_data['template_id'].sendgrid_id

        # Trigger the Celery task and get the result
        task = filter_sendgrid_events.delay(date_from, date_to, template_id)
        events = task.get()  # Wait for the task to complete and get the result

    return render(request, "msg/sendgrid_webhook_table.html", {
        "events": events,
        "form": form,
    })


def email_event_summary_view(request):
    form = TemplateFilterForm(request.GET or None)
    summary_table = ""

    # Only proceed with task if form is valid and template_id is provided
    if form.is_valid() and form.cleaned_data.get('template_id'):
        template_id = form.cleaned_data['template_id'].sendgrid_id

        # Call the Celery task
        result = generate_email_event_summary.delay(template_id)
        summary_table = result.get(timeout=10)  # Wait for task completion

    return render(request, "msg/email_event_summary_table.html", {
        "summary_table": summary_table,
        "form": form,
    })


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

