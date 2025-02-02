from __future__ import absolute_import, unicode_literals

import csv
import os
from datetime import datetime, timedelta

import pandas as pd
from celery.utils.log import get_task_logger
from django.conf import settings
from django.contrib.auth.models import Group
from django.db import connection
from django.db.models import F, Func, IntegerField, OuterRef, Subquery
from django.utils import timezone

from arl.celery import app
from arl.msg.models import EmailEvent, EmailTemplate, Message, SmsLog
from arl.user.models import CustomUser

from .helpers import (client, create_master_email, create_single_csv_email,
                      send_bulk_sms, send_monthly_store_phonecall,
                      send_sms_model, send_whats_app_template,
                      send_whats_app_template_autoreply,
                      sync_contacts_with_sendgrid)

logger = get_task_logger(__name__)


# this is the master email task.
@app.task(name="master_email_send")
def master_email_send_task(recipients, sendgrid_id, attachments=None):
    """
    Master task to send emails using the provided template and recipient data.

    Args:
        recipients (list): List of dictionaries containing recipient
        data (name, email).
        sendgrid_id (str): SendGrid template ID to use for the email.
        attachments (list, optional): List of attachments 
        (each as a dictionary with file details).

    Returns:
        str: Success or error message.
    """
    try:
        # Track errors and successes
        failed_emails = []
        for recipient in recipients:
            try:
                email = recipient.get("email")
                name = recipient.get("name")

                if not email:
                    print(f"Skipping recipient with no email: {recipient}")
                    continue  # Skip if no email is provided

                # Call the helper function to send the email
                success = create_master_email(
                    to_email=email,
                    name=name,
                    sendgrid_id=sendgrid_id,
                    attachments=attachments,
                )
                if not success:
                    failed_emails.append(email)
                    print(f"Failed to send email to {email}.")
            except Exception as e:
                email_address = email or "Unknown"
                failed_emails.append(email_address)
                print(f"Error sending email to {email_address}: {e}")
        # Final status message
        if failed_emails:
            print(f"Emails sent with some failures. Failed emails: {failed_emails}")
            return f"Emails sent with some failures. Failed emails: {', '.join(failed_emails)}"
        else:
            print(f"All emails sent successfully using template '{sendgrid_id}'.")
            return f"All emails sent successfully using template '{sendgrid_id}'."

    except Exception as e:
        # Handle task-wide errors
        error_message = f"Critical error in master_email_send_task: {str(e)}"
        print(error_message)
    return error_message

# SMS tasks


@app.task(name="sms")
def send_sms_task(phone_number, message):
    try:
        send_sms_model(phone_number, message)
        return "Text message sent successfully"
    except Exception as e:
        return str(e)


@app.task(name="tobacco_compliance_sms_with_download_link")
def send_bulk_tobacco_sms_link():
    try:
        active_users = CustomUser.objects.filter(is_active=True)
        gsat = [user.phone_number for user in active_users]
        pdf_url = "https://boysenberry-poodle-7727.twil.io/assets/Required%20Action%20Policy%20for%20Tobacco%20and%20Vape%20single%20page-1.jpg"
        message = (
            "Attached is a link to our REQUIRED policy on Tobacco and "
            "Vape. "
            "Please review: "
            f"{pdf_url}. "
        )

        send_bulk_sms(gsat, message)
        # Log the result
        logger.info("Bulk SMS task completed successfully")
        log_message = f"Bulk SMS sent successfully to {', '.join(gsat)}"
        log_entry = SmsLog(level="INFO", message=log_message)
        log_entry.save()
    except Exception as e:
        # Log or handle other exceptions
        logger.error(f"An error occurred: {str(e)}")


@app.task(name="bulk_sms")
def send_bulk_sms_task():
    try:
        active_users = CustomUser.objects.filter(is_active=True)
        gsat = [user.phone_number for user in active_users]
        message = (
            "Required Action Policy for Tobacco and Vape Products WHAT IS "
            "REQUIRED? You must request ID from anyone purchasing tobacco "
            "or vape products, who looks to be younger than 40. WHY? It is "
            "against the law to sell tobacco or vape products to minors. "
            "A person who distributes tobacco or vape products to a minor "
            "is guilty of an offence, and could be punished with: Loss of "
            "employment. Face personal fines of $4,000 to $100,000. Loss of "
            "license to sell tobacco and vape products, as well as face "
            "additional fines of $10,000 to $150,000. (for the Associate) "
            "WHO? Each and every Guest that wants to buy tobacco products. "
            "REQUIRED Guests that look under the age of 40 are asked for "
            "(picture) I.D. when purchasing tobacco products. Ask for "
            "(picture) I.D. if they look under 40 before quoting the price "
            "of tobacco products. Ask for (picture) I.D. if they look under "
            "40 before placing tobacco products on the counter. Dont let an "
            "angry Guest stop you from asking for (picture) I.D. "
            "ITs THE LAW! I.D. Drivers license Passport Certificate of "
            "Canadian Citizenship Canadian permanent resident card "
            "Canadian Armed Forces I.D. card Any documents issued by a "
            "federal or provincial authority or a foreign government that"
            "contain a photo, date of birth and signature are also "
            "acceptable. IMPORTANT - School I.D. cannot be accepted as "
            "proof of age. EXPECTED RESULTS. No employee is charged with "
            "selling tobacco products to a minor. Employees always remember "
            "to ask for I.D. No Employee receives a warning letter about "
            "selling to a minor.",
        )
        send_bulk_sms(gsat, message)
        # Log the result
        logger.info("Bulk SMS task completed successfully")
        log_message = f"Bulk SMS sent successfully to {', '.join(gsat)}"
        log_entry = SmsLog(level="INFO", message=log_message)
        log_entry.save()
    except Exception as e:
        # Log or handle other exceptions
        logger.error(f"An error occurred: {str(e)}")


@app.task(name="one_off_bulk_sms")
def send_one_off_bulk_sms_task(group_id, message):
    try:
        group = Group.objects.get(pk=group_id)
        users_in_group = group.user_set.filter(is_active=True)
        gsat = [user.phone_number for user in users_in_group]
        message = message
        send_bulk_sms(gsat, message)
        # Log the result
        logger.info("Bulk SMS task completed successfully")
        log_message = f"Bulk SMS sent successfully to {', '.join(gsat)}"
        log_entry = SmsLog(level="INFO", message=log_message)
        log_entry.save()
    except Exception as e:
        # Log or handle other exceptions
        logger.error(f"An error occurred: {str(e)}")


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
            timestamp = timezone.datetime.fromtimestamp(event_data.get("timestamp", 0), tz=timezone.utc)
            ip = event_data.get("ip", "192.0.2.0")  # Default IP
            url = event_data.get("url", "")
            useragent = event_data.get("useragent", "")

            # Find the associated user
            try:
                user = CustomUser.objects.get(email=email)
            except CustomUser.DoesNotExist:
                user = None
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
                username=user.username if user else None,
                useragent=useragent,
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
def generate_email_event_summary(template_id=None, start_date=None,
                                 end_date=None):
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
    customuser_subquery = CustomUser.objects.filter(
        email=OuterRef('email')
    ).annotate(
        store_number_int=Func(F('store__number'), function='FLOOR',
                              output_field=IntegerField())
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
    # If no data is available in the queryset
    if not event_data:
        return "<p>No email events found for the given filters.</p>"
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
    remaining_columns = [col for col in summary_df.columns if
                         col not in desired_columns]
    final_column_order = desired_columns + sorted(remaining_columns)

    summary_df = summary_df[final_column_order]

    # Convert the summary DataFrame to HTML and return
    return summary_df.to_html(classes="table table-striped",
                              index=False, table_id="table_sms")


@app.task(name="email_campaign_automation")
def start_campaign_task(selected_list_id):
    """Sync contacts and schedule the campaign."""
    # Sync contacts to the selected list in SendGrid
    sync_contacts_with_sendgrid(selected_list_id)

    # Log or manage start/end dates for your campaign as needed
    print(f"Campaign scheduled for list {selected_list_id}.")


@app.task(name="send_weekly_tobacco_email")
def send_weekly_tobacco_email():
    success_message = "Weekly Tobacco Emails Sent Successfully"
    template_id = "d-488749fd81d4414ca7bbb2eea2b830db"
    attachments = None
    try:
        active_users = CustomUser.objects.filter(is_active=True)
        for user in active_users:
            create_master_email(user.email, user.username, template_id, attachments)
        return success_message
    except CustomUser.DoesNotExist:
        logger.warning("No active users found to send tobacco emails.")
        return success_message

    except Exception as e:
        error_message = f"Failed to send tobacco emails. Error: {str(e)}"
        logger.error(error_message)
        return error_message


@app.task(name="monthly_store_calls")
def monthly_store_calls_task():
    try:
        send_monthly_store_phonecall()
        return "Monthly Phone Calls sent successfully"
    except Exception as e:
        return str(e)


@app.task(naem="get_twilio_messsage_summary")
def fetch_twilio_summary():
    try:
        # Fetch messages and calls
        messages = client.messages.list(limit=1000)
        calls = client.calls.list(limit=1000)

        # Separate messages into SMS and WhatsApp
        sms_data = []
        whatsapp_data = []
        call_data = []

        for message in messages:
            if message.price:
                data = {
                    'date_sent': message.date_sent.strftime('%Y-%m'),
                    'price': float(message.price),
                }
                if 'whatsapp:' in message.from_ or 'whatsapp:' in message.to:
                    whatsapp_data.append(data)
                else:
                    sms_data.append(data)

        for call in calls:
            if call.price:
                call_data.append({
                    'date_sent': call.start_time.strftime('%Y-%m'),
                    'price': float(call.price),
                })

        # Function to summarize by month
        def summarize_by_month(data):
            df = pd.DataFrame(data)
            if df.empty:
                return pd.DataFrame(columns=['date_sent', 'price'])

            df['date_sent'] = pd.to_datetime(df['date_sent']).dt.to_period('M')
            summary = df.groupby('date_sent')['price'].sum().reset_index()
            summary['date_sent'] = summary['date_sent'].astype(str)  # Convert period to string
            return summary

        # Summarize each category
        sms_df = summarize_by_month(sms_data).rename(columns={'price': 'sms_price'})
        whatsapp_df = summarize_by_month(whatsapp_data).rename(columns={'price': 'whatsapp_price'})
        call_df = summarize_by_month(call_data).rename(columns={'price': 'call_price'})

        # ✅ Merge all categories
        all_months = pd.concat([sms_df, whatsapp_df, call_df], axis=0)['date_sent'].unique()
        all_months_df = pd.DataFrame({'date_sent': all_months})

        final_df = (
            all_months_df
            .merge(sms_df, on='date_sent', how='left')
            .merge(whatsapp_df, on='date_sent', how='left')
            .merge(call_df, on='date_sent', how='left')
        )

        # ✅ Fill NaN values with 0
        final_df.fillna(0, inplace=True)

        # ✅ Compute total price
        final_df['total_price'] = final_df['sms_price'] + final_df['whatsapp_price'] + final_df['call_price']

        # ✅ Sort by month
        final_df = final_df.sort_values(by='date_sent', ascending=False)

        final_summary = final_df.to_dict('records')

        # ✅ Debugging Output
        print("🔍 Final Summary Data:", final_summary)

        return {
            "sms_summary": sms_df.to_dict('records'),
            "whatsapp_summary": whatsapp_df.to_dict('records'),
            "call_summary": call_df.to_dict('records'),
            "summary": final_summary,  # ✅ Ensuring this is populated
        }

    except Exception as e:
        print(f"Error fetching or processing Twilio messages: {e}")
        raise e
    
    
@app.task(name="generate_employee_email_report")
def generate_employee_email_report_task(employee_id):
    # Fetch the employee's email using the ID
    employee = CustomUser.objects.get(pk=employee_id)
    email = employee.email

    # Fetch template IDs for templates marked as "include_in_report"
    template_ids = EmailTemplate.objects.filter(
        include_in_report=True).values_list('sendgrid_id', flat=True)
    # print(template_ids)
    # Search for all email events related to this email address
    email_events = EmailEvent.objects.filter(email=email,
                                             sg_template_id__in=template_ids)

    # Summarize the events into a DataFrame
    event_data = list(email_events.values('event', 'sg_template_name'))
    if not event_data:
        return "<p>No data found for this employee.</p>"

    # Create DataFrame
    df = pd.DataFrame(event_data)

    # Check if the DataFrame is empty
    if df.empty:
        return "<p>No data found for this employee.</p>"

    # Pivot table to summarize events
    summary_df = df.pivot_table(
        index='sg_template_name',
        columns='event',
        aggfunc='size',
        fill_value=0
    ).reset_index()

    # Capitalize column names
    summary_df.columns = [str(col).capitalize() for col in summary_df.columns]

    # Convert DataFrame to HTML
    return summary_df.to_html(
        classes="table table-striped",
        index=False,
        table_id="table_email_report"
    )


@app.task(name="fetch_twilio_sms_task")
def fetch_twilio_sms_task():
    """
    Fetch SMS messages from Twilio and process them.
    Returns a list of processed message data.
    """
    messages = client.messages.list(limit=1000)

    sms_data = []
    for msg in messages:
        truncated_body = msg.body[:250]
        user = CustomUser.objects.filter(phone_number=msg.to).first()
        username = f"{user.first_name} {user.last_name}" if user else None
        sms_data.append({
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
            "username": username,
        })
    return sms_data
