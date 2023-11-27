from __future__ import absolute_import, unicode_literals

import json
from io import BytesIO

import pdfkit
import requests
from celery.exceptions import SoftTimeLimitExceeded
from celery.utils.log import get_task_logger
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify

from arl.celery import app
from arl.dsign.helpers import create_docusign_envelope, get_docusign_envelope
from arl.helpers import get_s3_images_for_incident, upload_to_linode_object_storage
from arl.incident.models import Incident
from arl.msg.helpers import (
    client,
    create_email,
    create_hr_newhire_email,
    create_single_email,
    create_tobacco_email,
    notify_service_sid,
    send_bulk_sms,
    send_monthly_store_phonecall,
    send_sms_model,
)
from arl.msg.models import EmailEvent, EmailTemplate, SmsLog
from arl.user.models import CustomUser

logger = get_task_logger(__name__)


@app.task(name="sms")
def send_sms_task(phone_number, message):
    try:
        send_sms_model(phone_number, message)
        return "Text message sent successfully"
    except Exception as e:
        return str(e)


@app.task(name="send_weekly_tobacco_email")
def send_weekly_tobacco_email():
    success_message = "Weekly Tobacco Emails Sent Successfully"
    try:
        active_users = CustomUser.objects.filter(is_active=True)
        for user in active_users:
            create_tobacco_email(user.email, user.username)
        return success_message
    except CustomUser.DoesNotExist:
        logger.warning("No active users found to send tobacco emails.")
        return success_message

    except Exception as e:
        error_message = f"Failed to send tobacco emails. Error: {str(e)}"
        logger.error(error_message)
        return error_message


# this task is for emails with a template id from sendgrid.
@app.task(name="send_template_email")
def send_template_email_task(group_id, subject, sendgrid_id):
    try:
        # Retrieve all users within the group
        group = Group.objects.get(pk=group_id)
        users_in_group = group.user_set.all()
        # Retrieve the template name based on the sendgrid_id
        template = EmailTemplate.objects.get(sendgrid_id=sendgrid_id)
        template_name = template.name
        for user in users_in_group:
            create_email(user.email, subject, user.first_name, sendgrid_id)

        return f"Template '{template_name}' Emails Sent Successfully"

    except Exception as e:
        return str(e)


@app.task(name="send_email")
def send_email_task(to_email, subject, name):
    try:
        create_single_email(to_email, subject, name)
        return "Email Sent Successfully"
    except Exception as e:
        return str(e)


@app.task(name="bulk_sms")
def send_bulk_sms_task():
    try:
        active_users = CustomUser.objects.filter(is_active=True)
        gsat = [user.phone_number for user in active_users]
        message = (
            "Required Action Policy for Tobacco and Vape Products WHAT IS REQUIRED? You must request ID from anyone purchasing tobacco or vape products, who looks to be younger than 40. WHY? It is against the law to sell tobacco or vape products to minors. A person who distributes tobacco or vape products to a minor is guilty of an offence, and could be punished with: Loss of employment. Face personal fines of $4,000 to $100,000. Loss of license to sell tobacco and vape products, as well as face additional fines of $10,000 to $150,000. (for the Associate) WHO? Each and every Guest that wants to buy tobacco products. REQUIRED Guests that look under the age of 40 are asked for (picture) I.D. when purchasing tobacco products. Ask for (picture) I.D. if they look under 40 before quoting the price of tobacco products. Ask for (picture) I.D. if they look under 40 before placing tobacco products on the counter. Dont let an angry Guest stop you from asking for (picture) I.D. ITs THE LAW! I.D. Drivers license Passport Certificate of Canadian Citizenship Canadian permanent resident card Canadian Armed Forces I.D. card Any documents issued by a federal or provincial authority or a foreign government that contain a photo, date of birth and signature are also acceptable. IMPORTANT - School I.D. cannot be accepted as proof of age. EXPECTED RESULTS. No employee is charged with selling tobacco products to a minor. Employees always remember to ask for I.D. No Employee receives a warning letter about selling to a minor.",
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


@app.task(name="monthly_store_calls")
def monthly_store_calls_task():
    try:
        send_monthly_store_phonecall()
        return "Monthly Phone Calls sent successfully"
    except Exception as e:
        return str(e)


@app.task(name="create_incident_pdf")
def generate_pdf_task(incident_id, user_email):
    try:
        # Fetch incident data based on incident_id
        try:
            incident = Incident.objects.get(pk=incident_id)
        except ObjectDoesNotExist:
            raise ValueError("Incident with ID {} does not exist.".format(incident_id))

        images = get_s3_images_for_incident(
            incident.image_folder, incident.user_employer
        )
        context = {"incident": incident, "images": images}
        html_content = render_to_string("incident/incident_form_pdf.html", context)
        #  Generate the PDF using pdfkit
        options = {
            "enable-local-file-access": None,
            "--keep-relative-links": "",
            "encoding": "UTF-8",
        }
        pdf = pdfkit.from_string(html_content, False, options)
        #  Create a BytesIO object to store the PDF content
        pdf_buffer = BytesIO(pdf)
        # Create a unique file name for the PDF
        store_number = incident.store.number  # Replace with your actual attribute name
        brief_description = (
            incident.brief_description
        )  # Replace with your actual attribute name
        # Create a unique file name for the PDF using store number and brief description
        pdf_filename = f"{store_number}_{slugify(brief_description)}_report.pdf"
        # Save the PDF to a temporary location
        # with open(pdf_filename, "wb") as pdf_file:
        #    pdf_file.write(pdf_buffer.getvalue())
        # Close the BytesIO buffer to free up resources
        #  Set the BytesIO buffer's position to the beginning
        # Upload the PDF to Linode Object Storage
        object_key = f"SITEINCIDENT/{incident.user_employer}/INCIDENTPDF/{pdf_filename}"
        upload_to_linode_object_storage(pdf_buffer, object_key)
        pdf_buffer.seek(0)
        #  Close the BytesIO buffer to free up resources
        subject = "Your Incident Report"
        body = "Thank you for using our services. Attached is your incident report."
        attachment_data = pdf_buffer.getvalue()

        # Call the create_single_email function with user_email and other details
        create_single_email(user_email, subject, body, pdf_buffer, pdf_filename)
        # create_single_email(user_email, subject, body, pdf_buffer)

        return {
            "status": "success",
            "message": "PDF generated and uploaded successfully",
        }
    except Exception as e:
        logger.error("Error in generate_pdf_task: {}".format(e))
        return {"status": "error", "message": str(e)}


@app.task(name="create_docusign_envelope")
def create_docusign_envelope_task(envelope_args):
    try:
        create_docusign_envelope(envelope_args)
        logger.info("Docusign envelope created successfully")
        return "Docusign envelope created successfully"
    except Exception as e:
        logger.error(f"Error creating Docusign envelope: {str(e)}")
        return f"Error creating Docusign envelope: {str(e)}"


@app.task(name="create_hr_newhire_email")
def create_newhiredata_email(**email_data):
    try:
        create_hr_newhire_email(**email_data)
        logger.info(f"New hire email created successfully for {email_data['email']}")
        return "New hire email created successfully"
    except Exception as e:
        logger.error(
            f"Error creating new hire email for {email_data['email']}: {str(e)}"
        )
        return f"Error creating new hire email: {str(e)}"


@app.task(name="sendgrid_webhook")
def process_sendgrid_webhook(payload):
    try:
        if isinstance(payload, list) and len(payload) > 0:
            event_data = payload[0]
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
        return "Sendgrid Webhook Entry Made"
    except Exception as e:
        return str(e)


@app.task(name="docusign_webhook")
def process_docusign_webhook(payload):
    try:
        if "data" in payload and "envelopeSummary" in payload["data"]:
            envelope_summary = payload["data"]["envelopeSummary"]
            status = envelope_summary.get("status")
            if status == "sent":
                recipients = envelope_summary.get("recipients", {})
                signers = recipients.get("signers", [])

                if signers:
                    recipient = signers[0]  # Assuming first signer is the recipient
                    recipient_name = recipient.get("name", "")
                    recipient_email = recipient.get("email", "")
                    hr_users = CustomUser.objects.filter(
                        Q(is_active=True) & Q(groups__name="HR")
                    ).values_list("phone_number", flat=True)
                    message_body = f"New Hire File sent to recipient: {recipient_name} {recipient_email}"
                    send_bulk_sms(hr_users, message_body)
                    logger.info(f"Sent SMS for 'sent' status to HR:{recipient_name} {message_body}")
                    return f"Sent SMS for 'sent' status to HR: {recipient_name} {message_body}"
            elif status == "completed":
                recipients = envelope_summary.get("recipients", {})
                signers = recipients.get("signers", [])

                if signers:
                    recipient = signers[0]  # Assuming first signer is the recipient
                    recipient_name = recipient.get("name", "")
                    recipient_email = recipient.get("email", "")
                    hr_users = CustomUser.objects.filter(
                        Q(is_active=True) & Q(groups__name="HR")
                    ).values_list("phone_number", flat=True)
                    message_body = f"New Hire File completed by:{recipient_name} {recipient_email}"
                    send_bulk_sms(hr_users, message_body)
                    envelope_id = envelope_summary.get("envelopeId")
                    get_docusign_envelope(envelope_id)
                    return f"Sent SMS for 'completed' status to HR:{recipient_name} {message_body}"
    except Exception as e:
        logger.error(f"Error processing DocuSign webhook: {str(e)}")
        return f"Error processing DocuSign webhook: {str(e)}"
