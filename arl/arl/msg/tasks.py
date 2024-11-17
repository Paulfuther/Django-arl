from __future__ import absolute_import, unicode_literals

import csv
import os
from datetime import datetime, timedelta

import pandas as pd
from celery.utils.log import get_task_logger
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.db.models import F, Func, IntegerField, OuterRef, Subquery
from django.utils import timezone

from arl.celery import app
from arl.msg.helpers import (create_single_csv_email, send_whats_app_template,
                             send_whats_app_template_autoreply,
                             sync_contacts_with_sendgrid)
from arl.msg.models import EmailEvent, Message
from arl.user.models import CustomUser

CustomUser = get_user_model()


logger = get_task_logger(__name__)


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

        return f"Whatsapp Template   Sent Successfully"

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

        return f"Whatsapp autoreply Sent Successfully"

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


@app.task(name="sendgrid_webhook")
def process_sendgrid_webhook(payload):
    try:
        if isinstance(payload, list) and len(payload) > 0:
            event_data = payload[0]
            # print(event_data)
            email = event_data.get("email", "")
            event = event_data.get("event", "")
            ip = event_data.get("ip", "")
            # Handle missing 'ip' value with a placeholder or default value
            if not ip:
                ip = "192.0.2.0"
            sg_event_id = event_data.get("sg_event_id", "")
            sg_message_id = event_data.get("sg_message_id", "")
            sg_template_id = event_data.get("sg_template_id", "")
            sg_template_name = event_data.get("sg_template_name", "")
            timestamp = timezone.datetime.fromtimestamp(
                event_data.get("timestamp", 0), tz=timezone.utc
            ) - timedelta(hours=5)
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
        return "Sendgrid Webhook Entry Made"
    except Exception as e:
        return str(e)


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
            events = events.filter(timestamp__gte=timezone.datetime.combine(
                date_from, timezone.datetime.min.time()))
        if date_to:
            events = events.filter(timestamp__lte=timezone.datetime.combine(
                date_to, timezone.datetime.max.time()))

        # Prefetch related store data for each user in the event
        events = events.select_related('user__store')

    # Convert events to a list of dictionaries for easier rendering
        event_data = list(events.values(
                'email',                 # User's email
                'user__username',        # User's username
                'user__store__number',   # Store identifier
                'event',                 # Event type
                'sg_event_id',
                'sg_template_name',      # Template name
                'timestamp'              # Timestamp of the event
            ))
    else:
        event_data = []

    return event_data


@app.task(name="email_event_summary")
def generate_email_event_summary(template_id=None):
    # Filter events based on template_id if provided
    events = EmailEvent.objects.all()
    if template_id:
        events = events.filter(sg_template_id=template_id)

    # Subquery to retrieve first_name, last_name from CustomUser and store number from Store
    customuser_subquery = CustomUser.objects.filter(
        email=OuterRef('email')
    ).annotate(
        store_number_int=Func(F('store__number'), function='FLOOR', output_field=IntegerField())
    ).values('first_name', 'last_name', 'store_number_int')

    # Annotate events with first_name, last_name, and integer store number
    events = events.annotate(
        first_name=Subquery(customuser_subquery.values('first_name')[:1]),
        last_name=Subquery(customuser_subquery.values('last_name')[:1]),
        store_number=Subquery(customuser_subquery.values('store_number_int')[:1])
    )

    # Convert events queryset to a DataFrame
    event_data = list(events.values(
        'email', 'event', 'sg_template_name', 'first_name', 'last_name', 'store_number'
    ))
    df = pd.DataFrame(event_data)

    # Group by template name, email, first_name, last_name, and store number, then pivot on the event type
    summary_df = df.pivot_table(
        index=['sg_template_name', 'email', 'first_name', 'last_name', 'store_number'],
        columns='event',
        aggfunc='size',
        fill_value=0
    ).reset_index()

    # Capitalize column names for display
    summary_df.columns = [col.capitalize() for col in summary_df.columns]

    # Define the desired column order
    desired_columns = ["Sg_template_name", "Email", "First_name", "Last_name", "Store_number", "Click", "Open"]

    # Add any missing columns with default value 0
    for col in desired_columns:
        if col not in summary_df.columns:
            summary_df[col] = 0

    # Reorder columns and add any remaining columns
    remaining_columns = [col for col in summary_df.columns if col not in desired_columns]
    final_column_order = desired_columns + sorted(remaining_columns)

    summary_df = summary_df[final_column_order]

    # Convert the summary DataFrame to HTML and return
    return summary_df.to_html(classes="table table-striped", index=False, table_id="table_sms")


@app.task(name="email_campaign_automation")
def start_campaign_task(selected_list_id):
    """Sync contacts and schedule the campaign."""
    # Sync contacts to the selected list in SendGrid
    sync_contacts_with_sendgrid(selected_list_id)

    # Log or manage start/end dates for your campaign as needed
    print(f"Campaign scheduled for list {selected_list_id}.")
