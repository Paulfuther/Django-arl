from __future__ import absolute_import, unicode_literals

import csv
import os
import requests
import base64
from datetime import datetime, timedelta
from django_celery_results.models import TaskResult
import pandas as pd
from celery.utils.log import get_task_logger
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.db.models import F, Func, IntegerField, OuterRef, Subquery
from django.utils import timezone
from twilio.rest import Client
from celery import Task
from arl.celery import app
from arl.msg.models import EmailEvent, EmailLog, EmailTemplate, Message, SmsLog
from arl.setup.models import TenantApiKeys
from arl.user.models import CustomUser, Employer, EmployerSMSTask, SMSOptOut

from .helpers import (
    client,
    create_master_email,
    create_single_csv_email,
    send_bulk_sms,
    send_monthly_store_phonecall,
    send_sms_model,
    send_whats_app_template,
    send_whats_app_template_autoreply,
    sync_contacts_with_sendgrid,
    send_linkshortened_sms
)

logger = get_task_logger(__name__)


#
# APPROVED
#
# This task is APPROVED for multi tenant.
# It is also the master email task.
@app.task(name="master_email_send")
def master_email_send_task(
        recipients,
        sendgrid_id,
        attachments=None,
        employer_id=None,
        body=None,
        subject=None,
        attachment_urls=None
        ):
    """
    Master task to send emails using the provided template and recipient data.

    Args:
        recipients (list): List of dictionaries containing recipient data (name, email).
        sendgrid_id (str): SendGrid template ID to use for the email.
        attachments (list, optional): List of attachments (each as a dictionary with file details).
        employer_id (int, optional): Employer ID for logging purposes.

    Returns:
        str: Success or error message.
    """
    attachment_urls = attachment_urls or []
    print("attachment urls :", attachment_urls)
    attachments = []
    for url in attachment_urls:
        try:
            response = requests.get(url)
            print(f"📡 Fetching: {url} → Status: {response.status_code}")
            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "application/octet-stream")
                filename = url.split("/")[-1]
                encoded = base64.b64encode(response.content).decode("utf-8")
                attachments.append({
                    "filename": filename,
                    "type": content_type,
                    "content": encoded,
                    "disposition": "attachment"
                })
            else:
                print(f"❌ Failed to fetch {url} → {response.status_code}")
        except Exception as e:
            print(f"🚨 Error fetching {url}: {e}")

    print("✅ Final attachments summary:")
    for a in attachments:
        print(f"• {a['filename']} ({a['type']}) - {len(a['content']) // 1024} KB")

    try:
        # Default sender
        verified_sender = settings.MAIL_DEFAULT_SENDER
        employer = None

        # Retrieve employer-specific verified sender
        if employer_id:
            employer = Employer.objects.filter(id=employer_id).first()
            if employer:
                tenant_api_key = TenantApiKeys.objects.filter(employer=employer).first()
                if tenant_api_key and tenant_api_key.verified_sender_email:
                    verified_sender = tenant_api_key.verified_sender_email

        print(f"📧 Using verified sender: {verified_sender}")

        failed_emails = []

        for recipient in recipients:
            email = recipient.get("email")
            name = recipient.get("name")

            if not email:
                print(f"Skipping recipient with no email: {recipient}")
                continue

            template_data = {
                "name": name,
                "body": body,
                "senior_contact_name": employer.senior_contact_name,
                "company_name": employer.name if employer else "Company",
                "subject": subject if subject else f"New Message from {employer.name if employer else 'Our Company'}",
            }

            success = create_master_email(
                to_email=email,
                sendgrid_id=sendgrid_id,
                template_data=template_data,
                attachments=attachments,
                verified_sender=verified_sender,
            )

            if not success:
                failed_emails.append(email)
                print(f"❌ Failed to send email to {email}")

        if failed_emails:
            return f"Emails sent with some failures. Failed emails: {', '.join(failed_emails)}"
        else:
            return f"✅ All emails sent successfully using template '{sendgrid_id}'"

    except Exception as e:
        error_message = f"🔥 Critical error in master_email_send_task: {str(e)}"
        print(error_message)
        return error_message
    

#
# APPROVED
#
# This task is APPROVED for multi tenant
# This task takes employers who want the tobacco sms and
# logs them and their users when sent.
# The logs are in the SmsLogs model
class TrackPeriodicNameTask(Task):
    def on_success(self, retval, task_id, args, kwargs):
        TaskResult.objects.filter(task_id=task_id).update(
            periodic_task_name="Tobacco Compliance SMS"
        )
        super().on_success(retval, task_id, args, kwargs)


@app.task(name="tobacco_compliance_sms_with_download_link",
          bind=True,
          base=TrackPeriodicNameTask,
          track_started=True,
          ignore_result=False,)
def send_bulk_tobacco_sms_link(self, *args, **kwargs):
    try:
        # Get Employers who have this SMS enabled
        enabled_employers = EmployerSMSTask.objects.filter(
            task_name="tobacco_compliance_sms_with_download_link", is_enabled=True
        ).values_list("employer_id", flat=True)

        if not enabled_employers:
            logger.warning("No employers enabled for this SMS task.")
            return

        # Get active users from employers who have SMS enabled
        opted_out_users = SMSOptOut.objects.values_list("user_id", flat=True)

        active_users = (
            CustomUser.objects.filter(is_active=True, employer_id__in=enabled_employers)
            .exclude(id__in=opted_out_users)
            .exclude(phone_number__isnull=True)
            .exclude(phone_number="")
        )
        # Get the unique employers from the active users
        # employer_names = Employer.objects.filter(id__in=enabled_employers).values_list("name", flat=True)
        # active_users = CustomUser.objects.filter(is_active=True)
        gsat = [str(user.phone_number) for user in active_users]
        print("numbers :", gsat)
        if not gsat:
            logger.warning("No valid phone numbers found to send SMS.")
            print("no valid phone numbers")
            return

        pdf_url = "https://boysenberry-poodle-7727.twil.io/assets/Required%20Action%20Policy%20for%20Tobacco%20and%20Vape%20single%20page-1.jpg"
        message = (
            "Attached is a link to our REQUIRED policy on Tobacco and "
            "Vape. "
            "Please review: "
            f"{pdf_url}. "
        )

        # Added
        results_summary = []

        # ✅ Process each employer separately to ensure correct Twilio credentials
        for employer_id in enabled_employers:
            employer = Employer.objects.get(id=employer_id)
            employer_users = active_users.filter(employer=employer)

            phone_numbers = [str(user.phone_number) for user in employer_users]
            if not phone_numbers:
                logger.warning(f"⚠️ No active users for employer: {employer.name}")
                continue

            # ✅ Fetch employer-specific Twilio credentials
            twilio_keys = TenantApiKeys.objects.filter(
                employer=employer, is_active=True
            ).first()

            if not twilio_keys:
                logger.error(
                    f"🚨 No Twilio API keys found for employer: {employer.name}. Skipping SMS."
                )
                continue

            twilio_account_sid = twilio_keys.account_sid
            twilio_auth_token = twilio_keys.auth_token
            twilio_notify_sid = twilio_keys.notify_service_sid
            if not twilio_account_sid or not twilio_auth_token or not twilio_notify_sid:
                logger.error(
                    f"🚨 Missing required Twilio credentials for employer: {employer.name}. Skipping SMS."
                )
                continue

            try:
                # ✅ Send SMS using employer's credentials
                send_bulk_sms(
                    phone_numbers,
                    message,
                    twilio_account_sid,
                    twilio_auth_token,
                    twilio_notify_sid,
                )

                # ✅ Log success per employer
                log_message = f"📢 Bulk Tobacco SMS sent successfully to {len(phone_numbers)} users for employer: {employer.name}"
                logger.info(log_message)
                SmsLog.objects.create(level="INFO", message=log_message)
                results_summary.append(f"✅ {log_message}")

                if not results_summary:
                    results_summary.append("ℹ️ Task ran successfully but no per-employer messages were recorded.")

            except Exception as e:
                # ✅ Log error per employer
                error_message = f"🚨 SMS Task Failed for {employer.name}: {str(e)}"
                logger.error(error_message)
                SmsLog.objects.create(level="ERROR", message=error_message)
                results_summary.append(error_message)

            # ✅ Set `periodic_task_name` in the results DB
        TaskResult.objects.filter(task_id=self.request.id).update(
            periodic_task_name="Tobacco Compliance SMS"
        )

        # ✅ Return clean result summary
        return {
            "summary": results_summary,
            "total_employers": len(enabled_employers),
            "successful": [msg for msg in results_summary if msg.startswith("✅")],
            "errors": [msg for msg in results_summary if msg.startswith("🚨")],
        }

    except Exception as e:
        critical_msg = f"🔥 CRITICAL error in task: {str(e)}"
        logger.critical(critical_msg)
        SmsLog.objects.create(level="CRITICAL", message=critical_msg)
        return {"error": critical_msg}


@app.task(name="tobacoo_sms_with_shortened_link",
          bind=True,)
def send_bulk_shortened_sms_link_task(self):
    try:
        enabled_employers = EmployerSMSTask.objects.filter(
            task_name="tobacco_compliance_sms_with_shortened_link",
            is_enabled=True
        ).values_list("employer_id", flat=True)

        if not enabled_employers:
            logger.warning("No employers enabled for this SMS task.")
            return

        opted_out_users = SMSOptOut.objects.values_list("user_id", flat=True)

        active_users = CustomUser.objects.filter(
            is_active=True,
            employer_id__in=enabled_employers
        ).exclude(id__in=opted_out_users)\
         .exclude(phone_number__isnull=True)\
         .exclude(phone_number="")
        print("Active Users :", active_users)
        results_summary = []

        for employer_id in enabled_employers:
            employer = Employer.objects.get(id=employer_id)
            employer_users = active_users.filter(employer=employer)

            phone_numbers = [str(user.phone_number) for user in employer_users]
            if not phone_numbers:
                logger.warning(f"⚠️ No active users for employer: {employer.name}")
                continue

            # Get Twilio credentials
            twilio_keys = TenantApiKeys.objects.filter(
                employer=employer,
                is_active=True
            ).first()

            if not twilio_keys:
                logger.error(f"🚨 No Twilio keys for {employer.name}")
                continue

            sid = twilio_keys.account_sid
            token = twilio_keys.auth_token
            msg_sid = twilio_keys.messaging_service_sid
            if not sid or not token or not msg_sid:
                logger.error(f"🚨 Incomplete Twilio credentials for {employer.name}")
                continue

            # Define message
            body = (
                "Hello, this is Terry from Petro Canada. Each week, we share reminders for employees "
                "about regulated products. Please review this week’s message: "
                "https://paulfuther.eu-central-1.linodeobjects.com/compliance/4dcc0432-05f8-4e5e-b462-7c31bd7c59bd_compliance/rules.pdf "
                "Reply STOP to opt out."
            )
            # Send individually to each user so link gets shortened per-message
            for phone in phone_numbers:
                result = send_linkshortened_sms(
                    to_number=phone,
                    body=body,
                    twilio_account_sid=sid,
                    twilio_auth_token=token,
                    twilio_message_service_sid=msg_sid,
                )
                logger.info(f"{employer.name}: {result}")

            results_summary.append(f"✅ Sent SMS to {len(phone_numbers)} for {employer.name}")

        TaskResult.objects.filter(task_id=self.request.id).update(
            periodic_task_name="Tobacco Compliance Shortened SMS"
        )

        return {
            "summary": results_summary,
            "total_employers": len(enabled_employers),
            "successful": [msg for msg in results_summary if msg.startswith("✅")],
        }

    except Exception as e:
        msg = f"🔥 CRITICAL error in task: {str(e)}"
        logger.critical(msg)
        SmsLog.objects.create(level="CRITICAL", message=msg)
        return {"error": msg}



# APPROVED
# This task is APPROVED for multi tenant.
# Tenatn api keys are geneated here and passed to the helper.
@app.task(name="one_off_bulk_sms")
def send_one_off_bulk_sms_task(group_id, message, user_id):
    User = get_user_model()
    try:
        # ✅ Get the user who initiated the SMS
        user = User.objects.get(id=user_id)
        employer = user.employer  # Assuming employer is a ForeignKey in User model

    except User.DoesNotExist:
        logger.error(f"🚨 User {user_id} not found.")
        return

    try:
        # ✅ Get the group and active users
        group = Group.objects.get(pk=group_id)
        users_in_group = group.user_set.filter(is_active=True, employer=employer)
        phone_numbers = [user.phone_number for user in users_in_group]

    except Group.DoesNotExist:
        logger.error(f"🚨 Group {group_id} not found.")
        return

    if not phone_numbers:
        logger.warning(
            f"⚠️ No active users in group {group.name}. Skipping SMS sending."
        )
        return

    # ✅ Get employer-specific Twilio credentials from TenantApiKeys
    twilio_keys = (
        TenantApiKeys.objects.filter(employer=employer, is_active=True)
        .values("account_sid", "auth_token", "notify_service_sid")
        .first()
    )
    print("Employer, Twilio keys :", employer, twilio_keys)
    if not twilio_keys:
        logger.error(
            f"🚨 No active Twilio credentials for employer: {employer.name}. SMS not sent."
        )
        return

    twilio_account_sid = twilio_keys.get("account_sid")
    twilio_auth_token = twilio_keys.get("auth_token")
    twilio_notify_sid = twilio_keys.get("notify_service_sid")

    if not twilio_account_sid or not twilio_auth_token or not twilio_notify_sid:
        logger.error(f"🚨 Missing Twilio credentials for employer: {employer.name}.")
        return

    try:
        # ✅ Send bulk SMS, now including employer info
        send_bulk_sms(
            phone_numbers,
            message,
            twilio_account_sid,
            twilio_auth_token,
            twilio_notify_sid,
        )

        log_message = f"📢 Bulk SMS sent by {employer.name} to {group.name} ({len(phone_numbers)} recipients)"
        logger.info(log_message)

        SmsLog.objects.create(level="INFO", message=log_message)

    except Exception as e:
        logger.error(f"🚨 An error occurred while sending SMS: {str(e)}")


#
# APPROVED
#
# This task is APPROVED for multi tenant
# This task takes employers who want the tobacco email and
# logs them and their users when sent.
# The logs are in the SmsLogs model
@app.task(name="send_weekly_tobacco_email")
def send_weekly_tobacco_email():
    success_message = "Weekly Tobacco Emails Sent Successfully"
    template_id = "d-488749fd81d4414ca7bbb2eea2b830db"
    attachments = None

    try:
        # ✅ Get Employers who have this EMAIL enabled
        enabled_employers = EmployerSMSTask.objects.filter(
            task_name="send_weekly_tobacco_email", is_enabled=True
        ).values_list("employer_id", flat=True)

        if not enabled_employers:
            logger.warning("No employers enabled for this email task.")
            return success_message

        # ✅ Pre-fetch employers and store them in a dictionary (avoid multiple DB hits)
        employers = Employer.objects.filter(id__in=enabled_employers).values(
            "id", "name", "verified_sender_email"
        )
        employer_dict = {
            emp["id"]: {
                "name": emp["name"],
                "sender": emp["verified_sender_email"]
                if emp["verified_sender_email"]
                else settings.MAIL_DEFAULT_SENDER,
            }
            for emp in employers
        }

        # ✅ Fetch all active users in one query (reduce DB hits)
        active_users = CustomUser.objects.filter(
            is_active=True, employer_id__in=enabled_employers
        ).values("id", "email", "username", "employer_id")

        # ✅ Get template name in one query
        template_name = (
            EmailTemplate.objects.filter(sendgrid_id=template_id)
            .values_list("name", flat=True)
            .first()
            or "Unknown Template"
        )

        # ✅ Group users by employer_id
        employer_user_map = {}
        for user in active_users:
            employer_user_map.setdefault(user["employer_id"], []).append(user)

        # ✅ Loop through employers and process emails
        for employer_id, employer_info in employer_dict.items():
            users = employer_user_map.get(employer_id, [])
            verified_sender = employer_info["sender"]
            employer_name = employer_info["name"]

            email_sent = False

            # ✅ Process emails in bulk for efficiency
            for user in users:
                success = create_master_email(
                    to_email=user["email"],
                    sendgrid_id=template_id,
                    template_data={"name": user["username"]},
                    attachments=attachments,
                    verified_sender=verified_sender,  # ✅ Employer-specific sender
                )
                if success:
                    email_sent = True  # ✅ At least one email was successfully sent

            # ✅ Log **once per employer** (whether success or failure)
            EmailLog.objects.create(
                employer_id=employer_id,
                sender_email=verified_sender,
                template_id=template_id,
                template_name=template_name,
                status="SUCCESS" if email_sent else "FAILED",
            )

            logger.info(
                f"✅ Weekly Tobacco Email sent for employer: {employer_name} ({verified_sender})"
            )

        return success_message

    except Exception as e:
        logger.error(f"Error in send_weekly_tobacco_email: {e}", exc_info=True)
        return "Error sending weekly tobacco emails"


# SMS tasks
@app.task(name="sms")
def send_sms_task(phone_number, message):
    try:
        send_sms_model(phone_number, message)
        return "Text message sent successfully"
    except Exception as e:
        return str(e)


@app.task(name="send whatsapp")
def send_template_whatsapp_task(whatsapp_id, from_id, group_id):
    try:
        # Retrieve all users within the group
        print(whatsapp_id)
        group = Group.objects.get(pk=group_id)
        users_in_group = group.user_set.filter(is_active=True)
        # Retrieve the template name based on the whatsapp_id
        # template = WhatsAppTemplate.objects.get(whatsapp_id=whatsapp_id)
        # template_name = template.name
        for user in users_in_group:
            print(user.first_name, user.phone_number)
            send_whats_app_template(
                whatsapp_id, from_id, user.first_name, user.phone_number
            )

        return "Whatsapp Template   Sent Successfully"

    except Exception as e:
        return str(e)


@app.task(name="tobacco csv report")
def generate_and_save_csv_report():
    today = datetime.today()
    first_day_of_current_month = datetime(today.year, today.month, 1)
    last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
    first_day_of_previous_month = datetime(
        last_day_of_previous_month.year, last_day_of_previous_month.month, 1
    )
    start_date = first_day_of_previous_month.strftime("%Y-%m-%d")
    end_date = last_day_of_previous_month.strftime("%Y-%m-%d")
    sql_query = f"""
    SELECT email, event, sg_event_id, username FROM msg_emailevent
    WHERE timestamp BETWEEN '{start_date}' AND '{end_date}'
    AND sg_template_name = 'Tobacco Compliance'
    AND event IN ('open', 'click', 'delivered');
    """

    # Modify the file name to include the date range
    file_name = f"tobacco_report_{start_date}_to_{end_date}.csv"
    # Path where the CSV will be saved
    file_path = os.path.join(settings.MEDIA_ROOT, file_name)
    pivot_file_name = f"monthly_pivot_report_{start_date}_to_{end_date}.csv"
    pivot_file_path = os.path.join(settings.MEDIA_ROOT, pivot_file_name)
    with connection.cursor() as cursor:
        cursor.execute(sql_query)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()

    if not rows:
        return "No data available for the specified date range."

    try:
        with open(file_path, "w", newline="") as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(columns)
            csvwriter.writerows(rows)

        df = pd.read_csv(file_path)
        pivot_table = pd.pivot_table(
            df,
            values="sg_event_id",
            index=["email", "username"],
            columns="event",
            aggfunc="count",
            fill_value=0,
        )
        if {"delivered", "open", "click"}.issubset(pivot_table.columns):
            pivot_table = pivot_table[["delivered", "open", "click"]]
        pivot_table.sort_values(by="click", ascending=True, inplace=True)
        pivot_table.to_csv(pivot_file_path)

        # Email the report
        failure_messages = []
        for recipient in CustomUser.objects.filter(
            groups__name="email_tobacco_csv", is_active=True
        ):
            if not create_single_csv_email(
                to_email=recipient.email,
                subject=f"Monthly Tobacco Compliance Report ({start_date} to {end_date})",
                body="Attached is the monthly Tobacco Compliance report.",
                file_path=pivot_file_path,
            ):
                failure_messages.append(f"Failed to send report to {recipient.email}")

        if failure_messages:
            return "\n".join(failure_messages)

        return f"Tobacco Compliance report generated and emailed successfully to {recipient} at {recipient.email}"

    finally:
        # Clean up the generated files
        os.remove(file_path)
        os.remove(pivot_file_path)


@app.task(name="send whatsapp autoreply")
def send_template_whatsapp_autoreply_task(whatsapp_id, from_id, receiver):
    try:
        # Retrieve all users within the group
        print(whatsapp_id)
        # Retrieve the template name based on the whatsapp_id
        # template = WhatsAppTemplate.objects.get(whatsapp_id=whatsapp_id)
        # template_name = template.name
        send_whats_app_template_autoreply(whatsapp_id, from_id, receiver)

        return "Whatsapp autoreply Sent Successfully"

    except Exception as e:
        return str(e)


@app.task(name="process_whatsapp_webhook")
def process_whatsapp_webhook(data):
    try:
        print(data)

        # Determine message type
        message_type = "SMS" if "SmsMessageSid" in data else "WhatsApp"

        # Safely extract sender and receiver
        sender_raw = data.get("From", [""])[0]
        receiver_raw = data.get("To", [""])[0]
        sender = sender_raw.split(":")[1] if ":" in sender_raw else sender_raw
        receiver = receiver_raw.split(":")[1] if ":" in receiver_raw else receiver_raw

        message_status = data.get("MessageStatus", ["unknown"])[0]

        template_used = "TemplateId" in data

        # Fetch user or set to unknown
        username = "Unknown"
        if receiver:
            try:
                user = CustomUser.objects.get(phone_number=receiver)
                username = user.username
            except CustomUser.DoesNotExist:
                pass  # username remains "Unknown"
            except Exception as e:
                logger.error(f"Error fetching user by phone number {receiver}: {e}")

        # Create message record
        Message.objects.create(
            sender=sender,
            receiver=receiver,
            message_status=message_status,
            username=username,
            template_used=template_used,
            message_type=message_type,
        )

    except Exception as e:
        logger.error(f"Error processing webhook data: {e}")
        return {"status": "error", "message": "Internal Server Error"}
    return {"status": "success"}


# Approved for multi tenant
@app.task(name="sendgrid_webhook")
def process_sendgrid_webhook(payload):
    try:
        if not isinstance(payload, list) or len(payload) == 0:
            logger.warning("Invalid or empty payload received.")
            return "No events to process."

        for event_data in payload:
            email = event_data.get("email", "")
            sg_event_id = event_data.get("sg_event_id", "")
            sg_message_id = event_data.get("sg_message_id", "")
            sg_template_id = event_data.get("sg_template_id", "")
            sg_template_name = event_data.get("sg_template_name", "")
            event = event_data.get("event", "")
            timestamp = timezone.datetime.fromtimestamp(
                event_data.get("timestamp", 0), tz=timezone.utc
            )
            ip = event_data.get("ip", "192.0.2.0")  # Default IP
            url = event_data.get("url", "")
            useragent = event_data.get("useragent", "")

            # Find the associated user
            user = None
            employer = None
            try:
                user = CustomUser.objects.get(email=email)
                employer = user.employer  # Get employer from user if exists
            except CustomUser.DoesNotExist:
                logger.warning(f"User with email {email} not found.")

            # Save the email event
            EmailEvent.objects.create(
                email=email,
                event=event,
                ip=ip,
                sg_event_id=sg_event_id,
                sg_message_id=sg_message_id,
                sg_template_id=sg_template_id,
                sg_template_name=sg_template_name,
                timestamp=timestamp,
                url=url,
                user=user,
                username=user.username if user else "unknown",
                useragent=useragent,
                employer=employer
            )
            logger.info(f"Processed SendGrid event: {event} for {email}")

        return "SendGrid Webhook Events Processed Successfully."
    except Exception as e:
        logger.error(f"Error processing SendGrid webhook: {str(e)}", exc_info=True)
        return f"Error: {str(e)}"


@app.task(name="filter_sendgrid_events")
def filter_sendgrid_events(date_from=None, date_to=None, template_id=None):
    # Initialize the queryset
    events = EmailEvent.objects.none()

    # Ensure template_id is provided
    if template_id:
        # Filter events based on template_id
        events = EmailEvent.objects.filter(sg_template_id=template_id)

        # Apply date filters if provided
        if date_from:
            events = events.filter(
                timestamp__gte=timezone.datetime.combine(
                    date_from, timezone.datetime.min.time()
                )
            )
        if date_to:
            events = events.filter(
                timestamp__lte=timezone.datetime.combine(
                    date_to, timezone.datetime.max.time()
                )
            )

        # Prefetch related store data for each user in the event
        events = events.select_related("user__store")

        # Convert events to a list of dictionaries for easier rendering
        event_data = list(
            events.values(
                "email",  # User's email
                "user__username",  # User's username
                "user__store__number",  # Store identifier
                "event",  # Event type
                "sg_event_id",
                "sg_template_name",  # Template name
                "timestamp",  # Timestamp of the event
            )
        )
    else:
        event_data = []

    return event_data


@app.task(name="email_event_summary")
def generate_email_event_summary(template_id=None, start_date=None, end_date=None):
    # Filter events based on template_id if provided
    events = EmailEvent.objects.all()
    if template_id:
        events = events.filter(sg_template_id=template_id)

    # Apply date range filtering if provided
    if start_date:
        events = events.filter(timestamp__gte=start_date)
    if end_date:
        events = events.filter(timestamp__lte=end_date)
    # Check if there are no events after filtering
    if not events.exists():
        return "<p>No email events found for the given filters.</p>"
    # Subquery to retrieve first_name, last_name from CustomUser
    # and store number from Store
    customuser_subquery = (
        CustomUser.objects.filter(email=OuterRef("email"))
        .annotate(
            store_number_int=Func(
                F("store__number"), function="FLOOR", output_field=IntegerField()
            )
        )
        .values("first_name", "last_name", "store_number_int")
    )

    # Annotate events with first_name, last_name, and integer store number
    events = events.annotate(
        first_name=Subquery(customuser_subquery.values("first_name")[:1]),
        last_name=Subquery(customuser_subquery.values("last_name")[:1]),
        store_number=Subquery(customuser_subquery.values("store_number_int")[:1]),
    )

    # Convert events queryset to a DataFrame
    event_data = list(
        events.values(
            "email",
            "event",
            "sg_template_name",
            "first_name",
            "last_name",
            "store_number",
        )
    )
    # If no data is available in the queryset
    if not event_data:
        return "<p>No email events found for the given filters.</p>"
    df = pd.DataFrame(event_data)

    # Group by template name, email, first_name, last_name, and store number, then pivot on the event type
    summary_df = df.pivot_table(
        index=["sg_template_name", "email", "first_name", "last_name", "store_number"],
        columns="event",
        aggfunc="size",
        fill_value=0,
    ).reset_index()

    # Capitalize column names for display
    summary_df.columns = [col.capitalize() for col in summary_df.columns]

    # Define the desired column order
    desired_columns = [
        "Sg_template_name",
        "Email",
        "First_name",
        "Last_name",
        "Store_number",
        "Click",
        "Open",
    ]

    # Add any missing columns with default value 0
    for col in desired_columns:
        if col not in summary_df.columns:
            summary_df[col] = 0

    # Reorder columns and add any remaining columns
    remaining_columns = [
        col for col in summary_df.columns if col not in desired_columns
    ]
    final_column_order = desired_columns + sorted(remaining_columns)

    summary_df = summary_df[final_column_order]

    # Convert the summary DataFrame to HTML and return
    return summary_df.to_html(
        classes="table table-striped", index=False, table_id="table_sms"
    )


@app.task(name="email_campaign_automation")
def start_campaign_task(selected_list_id):
    """Sync contacts and schedule the campaign."""
    # Sync contacts to the selected list in SendGrid
    sync_contacts_with_sendgrid(selected_list_id)

    # Log or manage start/end dates for your campaign as needed
    print(f"Campaign scheduled for list {selected_list_id}.")


@app.task(name="monthly_store_calls")
def monthly_store_calls_task():
    try:
        send_monthly_store_phonecall()
        return "Monthly Phone Calls sent successfully"
    except Exception as e:
        return str(e)


@app.task(naem="get_twilio_messsage_summary")
def fetch_twilio_summary():
    """Fetch Twilio SMS costs (including carrier fees) for the past 12 months."""
    try:

        def get_costs(start_date, end_date, category):
            """Fetch costs for a specific category within a date range."""
            records = client.usage.records.list(
                category=category, start_date=start_date, end_date=end_date
            )
            return sum(float(record.price) for record in records if record.price)

        # ✅ Define date ranges for past 12 months
        today = datetime.utcnow()
        months = [
            (today.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
            for i in range(12)
        ]
        sms_summary = []

        for month in months:
            start_date = month.strftime("%Y-%m-%d")
            end_date = (month.replace(day=28) + timedelta(days=4)).replace(
                day=1
            ) - timedelta(days=1)
            end_date = end_date.strftime("%Y-%m-%d")

            sms_cost = get_costs(start_date, end_date, "sms")
            calls_cost = get_costs(start_date, end_date, "calls")
            authy_sms_cost = get_costs(start_date, end_date, "authy-sms-outbound")
            authy_calls_cost = get_costs(start_date, end_date, "authy-calls-outbound")
            verify_sms_cost = get_costs(
                start_date, end_date, "verify-push"
            )  # Might not be exactly SMS
            verify_whatsapp_cost = get_costs(
                start_date, end_date, "verify-whatsapp-conversations-business-initiated"
            )
            carrier_fees = get_costs(start_date, end_date, "sms-messages-carrierfees")
            total_cost = get_costs(
                start_date, end_date, "totalprice"
            )  # Includes all fees

            sms_summary.append(
                {
                    "date_sent": month.strftime("%Y-%m"),
                    "sms_price": round(sms_cost, 2),
                    "calls_price": round(calls_cost, 2),
                    "authy_sms_price": round(authy_sms_cost, 2),
                    "authy_calls_price": round(authy_calls_cost, 2),
                    "verify_sms_price": round(verify_sms_cost, 2),
                    "verify_whatsapp_price": round(verify_whatsapp_cost, 2),
                    "carrier_fees": round(carrier_fees, 2),
                    "total_price": round(total_cost, 2),
                }
            )
        return {"sms_summary": sms_summary}
    except Exception as e:
        return {
            "sms_summary": [],
            "error": str(e),
        }


@app.task(name="generate_employee_email_report")
def generate_employee_email_report_task(employee_id):
    # Fetch the employee's email using the ID
    employee = CustomUser.objects.get(pk=employee_id)
    email = employee.email

    # Fetch template IDs for templates marked as "include_in_report"
    template_ids = EmailTemplate.objects.filter(include_in_report=True).values_list(
        "sendgrid_id", flat=True
    )
    # print(template_ids)
    # Search for all email events related to this email address
    email_events = EmailEvent.objects.filter(
        email=email, sg_template_id__in=template_ids
    )

    # Summarize the events into a DataFrame
    event_data = list(email_events.values("event", "sg_template_name"))
    if not event_data:
        return "<p>No data found for this employee.</p>"

    # Create DataFrame
    df = pd.DataFrame(event_data)

    # Check if the DataFrame is empty
    if df.empty:
        return "<p>No data found for this employee.</p>"

    # Pivot table to summarize events
    summary_df = df.pivot_table(
        index="sg_template_name", columns="event", aggfunc="size", fill_value=0
    ).reset_index()

    # Capitalize column names
    summary_df.columns = [str(col).capitalize() for col in summary_df.columns]

    # Convert DataFrame to HTML
    return summary_df.to_html(
        classes="table table-striped", index=False, table_id="table_email_report"
    )


# Approved for Multi Tenant Use.
# Fetches data based on keys for the users employer
@app.task(name="fetch_twilio_sms_task")
def fetch_twilio_sms_task(user_id):
    """
    Fetch Twilio SMS messages for a user's employer using their tenant API keys.
    """
    try:
        user = CustomUser.objects.get(id=user_id)
        employer = user.employer
        tenant_keys = TenantApiKeys.objects.get(employer=employer)
    except CustomUser.DoesNotExist:
        print("❌ User not found.")
        return []
    except TenantApiKeys.DoesNotExist:
        print(f"❌ No Twilio credentials found for employer {employer.name}.")
        return []

    try:
        client = Client(tenant_keys.account_sid, tenant_keys.auth_token)
        messages = client.messages.list(limit=1000)
    except Exception as e:
        print(f"❌ Error connecting to Twilio: {str(e)}")
        return []

    sms_data = []
    for msg in messages:
        truncated_body = msg.body[:250]
        matched_user = CustomUser.objects.filter(
            phone_number=msg.to, employer=employer
        ).first()

        sms_data.append(
            {
                "direction": msg.direction,
                "date_created": msg.date_created,
                "date_sent": msg.date_sent,
                "error_code": msg.error_code,
                "error_message": msg.error_message,
                "from": msg.from_,
                "to": msg.to,
                "status": msg.status,
                "price": msg.price,
                "price_unit": msg.price_unit,
                "body": truncated_body,
                "username": f"{matched_user.first_name} {matched_user.last_name}"
                if matched_user
                else None,
            }
        )

    return sms_data
