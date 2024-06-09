from __future__ import absolute_import, unicode_literals

import imaplib
import io
import json
import logging
import subprocess
from datetime import datetime, timedelta
from io import BytesIO

import pdfkit
from celery.utils.log import get_task_logger
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify
from docusign_esign import ApiClient, ApiException, EnvelopesApi

from arl.celery import app
from arl.dbox.helpers import upload_incident_file_to_dropbox
from arl.dsign.helpers import (
    create_docusign_envelope,
    create_docusign_envelope_new_hire_quiz,
    fetch_envelope_details,
    get_access_token,
    get_docusign_envelope,
    get_docusign_envelope_quiz,
    get_docusign_template_name_from_template,
    get_template_id,
)
from arl.dsign.models import DocuSignTemplate, ProcessedDocsignDocument
from arl.helpers import (
    get_s3_images_for_incident,
    remove_old_backups,
    upload_to_linode_object_storage,
)
from arl.incident.models import Incident
from arl.msg.helpers import (
    create_email,
    create_hr_newhire_email,
    create_incident_file_email,
    create_incident_file_email_by_rule,
    create_single_email,
    create_tobacco_email,
    send_bulk_sms,
    send_monthly_store_phonecall,
    send_sms_model,
)

from arl.msg.models import EmailEvent, EmailTemplate, SmsLog, WhatsAppTemplate
from arl.user.models import CustomUser, Employer, Store, UserManager

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
        users_in_group = group.user_set.filter(is_active=True)
        # Retrieve the template name based on the sendgrid_id
        template = EmailTemplate.objects.get(sendgrid_id=sendgrid_id)
        template_name = template.name
        for user in users_in_group:
            create_email(user.email, subject, user.first_name, sendgrid_id)

        return f"Template '{template_name}' Emails Sent Successfully"

    except Exception as e:
        return str(e)


@app.task(name="send_newhire_template_email")
def send_newhire_template_email_task(user_email, subject, user_first_name, sendgrid_id):
    try:
        # Retrieve the template name based on the sendgrid_id
        template = EmailTemplate.objects.get(sendgrid_id=sendgrid_id)
        template_name = template.name
        create_email(user_email, subject, user_first_name, sendgrid_id)

        return f"Template '{template_name}' Emails Sent Successfully"

    except Exception as e:
        return str(e)


@app.task(name="send_email")
def send_email_task(group_id, template_id, attachment=None):
    try:
        group = Group.objects.get(pk=group_id)
        users_in_group = group.user_set.filter(is_active=True)
        for user in users_in_group:

            create_single_email(user.email, user.first_name, template_id, attachment)
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


@app.task(name="monthly_store_calls")
def monthly_store_calls_task():
    try:
        send_monthly_store_phonecall()
        return "Monthly Phone Calls sent successfully"
    except Exception as e:
        return str(e)


# This task is used when a site incident form is first created.
# It takes the form, creates a pdf, then the following:
# Email are sent to incident_form_email group as well as
# Being uploaded to S3 and Dropbox


@app.task(name="create_incident_pdf")
def generate_pdf_task(incident_id):
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
        brief_description = incident.brief_description
        # Create a unique file name for the PDF using store number and brief description
        pdf_filename = f"{store_number}_{slugify(brief_description)}_report.pdf"

        # Close the BytesIO buffer to free up resources
        # Set the BytesIO buffer's position to the beginning
        # Upload the PDF to Linode Object Storage
        object_key = f"SITEINCIDENT/{incident.user_employer}/INCIDENTPDF/{pdf_filename}"
        upload_to_linode_object_storage(pdf_buffer, object_key)

        # Upload the PDF to Dropbox
        upload_incident_file_to_dropbox(pdf, pdf_filename)
        # Set the BytesIO buffer's position to the beginning
        pdf_buffer.seek(0)

        # Close the BytesIO buffer to free up resources
        # Then email to the current user and all users in
        # the group incident_form_email

        subject = "A New Incident Report Has Been Created"
        body = "Thank you for using our services. Attached is your incident report."
        # attachment_data = pdf_buffer.getvalue()

        # Call the create_incident_file_email_by_rule
        # user_email and other details

        to_emails = CustomUser.objects.filter(
            Q(is_active=True) & Q(groups__name="incident_form_email")
        ).values_list("email", flat=True)

        create_incident_file_email_by_rule(
            to_emails, subject, body, pdf_buffer, pdf_filename
        )

        return {
            "status": "success",
            "message": "PDF generated and uploaded successfully",
        }
    except Exception as e:
        logger.error("Error in generate_pdf_task: {}".format(e))
        return {"status": "error", "message": str(e)}


# This task creates a pdf of the select Incident Form
# Then emails the form to the user.
# This is called from the list of incidents
# when you click the pdf button
@app.task(name="email_updated_incident_pdf")
def generate_pdf_email_to_user_task(incident_id, user_email):
    try:
        # Fetch incident data based on incident_id
        try:
            incident = Incident.objects.get(pk=incident_id)
        except ObjectDoesNotExist:
            raise ValueError("Incident with ID {} does not exist.".format(incident_id))

        # get images, if there are any, from the s3 bucket
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
        # create the pdf
        pdf = pdfkit.from_string(html_content, False, options)
        #  Create a BytesIO object to store the PDF content
        pdf_buffer = BytesIO(pdf)
        # Create a unique file name for the PDF
        store_number = incident.store.number  # Replace with your actual attribute name
        brief_description = incident.brief_description
        # Create a unique file name for the PDF using store number and brief description
        pdf_filename = f"{store_number}_{slugify(brief_description)}_report.pdf"

        # Close the BytesIO buffer to free up resources
        # Then email to the current user

        subject = f"Your Incident Report {pdf_filename}"
        body = "Thank you for using our services. Attached is your incident report."
        # attachment_data = pdf_buffer.getvalue()

        # Call the create_single_email function with
        # user_email and other details
        create_incident_file_email(user_email, subject, body, pdf_buffer, pdf_filename)
        # create_single_email(user_email, subject, body, pdf_buffer)

        return {
            "status": "success",
            "message": f"Incident {pdf_filename} emailed to {user_email}",
        }
    except Exception as e:
        logger.error("Error in generate_pdf_task: {}".format(e))
        return {"status": "error", "message": str(e)}


@app.task(name="create_docusign_envelope")
def create_docusign_envelope_task(envelope_args):
    try:
        create_docusign_envelope(envelope_args)
        signer_name = envelope_args.get("signer_name")
        logger.info(
            f"Docusign envelope New Hire File for {signer_name} created successfully"
        )
        return f"Docusign envelope New Hire File for {signer_name} created successfully"
    except Exception as e:
        logger.error(
            f"Error creating Docusign envelope New Hire File for {signer_name}: {str(e)}"
        )
        return f"Error creating Docusign envelope New Hire File for {signer_name}: {str(e)}"


@app.task(name="create_hr_newhire_email")
def create_newhire_data_email(**email_data):
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


def get_template_name(template_id):
    try:
        template = DocuSignTemplate.objects.get(template_id=template_id)
        return template.template_name
    except DocuSignTemplate.DoesNotExist:
        return None


@app.task(name="docusign_webhook")
def process_docusign_webhook(payload):
    envelope_id = payload.get("data", {}).get("envelopeId", "")
    if not envelope_id:
        logging.error("Envelope ID not found in the payload.")
        return
    # Assuming get_template_id is defined to extract
    # the template ID from the payload
    template_id = get_template_id(payload)
    if not template_id:
        print("No Template ID found.")
        return
    else:
        print(f"Template ID: {template_id}")
    # Use the envelopeId to get the template name
    template_name = get_docusign_template_name_from_template(template_id)
    print(f"template name is:  {template_name}")
    # Extract status and envelope summary from the payload
    status = payload.get("event", "")
    print(f"Status: {status}")
    envelope_summary = payload.get("data", {}).get("envelopeSummary", {})
    recipients = envelope_summary.get("recipients", {})
    signers = recipients.get("signers", [])
    recipient = signers[0]  # Assuming the first signer is
    recipient_email = recipient.get("email", "")
    if status == "envelope-sent":

        recipients = envelope_summary.get("recipients", {})
        signers = recipients.get("signers", [])
        if signers:
            print(f"Template Name second time: {template_name}")

            recipient = signers[0]  # Assuming the first signer is
            # the recipient
            recipient_email = recipient.get("email", "")

            # Optionally, fetch and print the recipient user's details
            # from CustomUser model
            try:
                user = CustomUser.objects.get(email=recipient_email)
                full_name = user.get_full_name()

                # print("fullname", full_name)
                # print(f"{template_name} sent to: {full_name} at {recipient_email}")
                hr_users = CustomUser.objects.filter(
                    Q(is_active=True) & Q(groups__name="dsign_sms")
                ).values_list("phone_number", flat=True)
                message_body = (
                    f"{template_name} sent to: {full_name} at {recipient_email}"
                )
                send_bulk_sms(hr_users, message_body)
                logger.info(
                    f"Sent SMS for 'sent' status to HR:{full_name} {message_body}"
                )
                return f"Sent SMS for 'sent' status to HR: {full_name} {template_name} {message_body}"

            except CustomUser.DoesNotExist:
                logging.error(
                    f"User with email {recipient_email} not found in the database."
                )
            except Exception as e:
                logging.error(f"Error processing recipient data: {e}")

    elif status == "recipient-completed":
        # Check if the document is a Standard Release and exit if it is
        if "Standard Release" in template_name:
            print(
                f"Processed Standard Release for {recipient_email}, no further action."
            )
            return

        try:
            user = CustomUser.objects.get(email=recipient_email)
        except CustomUser.DoesNotExist:
            logging.error(
                f"User with email {recipient_email} not found in the database."
            )
            return  # Optionally handle the case where the user doesn't exist

        full_name = user.get_full_name()
        print(f"Template Name 3: {template_name}")

        if "New Hire File" in template_name:
            # Check if the user has already completed a new hire file
            user = CustomUser.objects.get(
                email=recipient_email
            )  # Assuming you have the user's email
            full_name = user.get_full_name()
            already_completed = ProcessedDocsignDocument.objects.filter(
                user=user, template_name="New Hire File"
            ).exists()
            if not already_completed:
                # Record this file to the db
                ProcessedDocsignDocument.objects.create(
                    user=user, envelope_id=template_id, template_name=template_name
                )
                # Logic to send another file called New Hire Quiz
                # The quiz is not sent here.
                # it is sent through a post save signal to the documents
                # model

                get_docusign_envelope(envelope_id, full_name, template_name)

                print(f"New Hire Quiz needs to be sent to {user.email}")
            else:
                print("User has already completed a New Hire File.")

            # get the file for uplad

            hr_users = CustomUser.objects.filter(
                Q(is_active=True) & Q(groups__name="dsign_sms")
            ).values_list("phone_number", flat=True)

            message_body = (
                f"{template_name} completed by: {full_name} at {recipient_email}"
            )
            send_bulk_sms(hr_users, message_body)
            logger.info(
                f"Sent SMS for 'completed' status to HR: {full_name} {message_body}"
            )
            return f"Sent SMS for 'completed' status to HR: {full_name} {template_name} {message_body}"
        else:
            # Record the completed non-new-hire file in
            # ProcessedDocsignDocument
            user = CustomUser.objects.get(email=recipient_email)
            print(full_name, recipient_email)
            ProcessedDocsignDocument.objects.create(
                user=user, envelope_id=template_id, template_name=template_name
            )
            print(f"Recorded completed file {template_name} for {user.email}")
            get_docusign_envelope_quiz(envelope_id, full_name, template_name)
            hr_users = CustomUser.objects.filter(
                Q(is_active=True) & Q(groups__name="dsign_sms")
            ).values_list("phone_number", flat=True)
            message_body = (
                f"{template_name} completed by: {full_name} at {recipient_email}"
            )
            send_bulk_sms(hr_users, message_body)
            logger.info(
                f"Sent SMS for 'completed' status to HR:{full_name} {message_body}"
            )
            return f"Sent SMS for 'completed' status to HR: {full_name} {template_name} {message_body}"

    print("Done.")


@app.task(name="postgress_backup")
def create_db_backup_and_upload():
    database_name = settings.DATABASES["default"]["NAME"]
    database_user = settings.DATABASES["default"]["USER"]
    # backup_file = settings.BACKUP_FILE_PATH_DEV
    pg_dump_path = settings.BACKUP_DUMP_PATH
    current_date = datetime.now().strftime("%Y-%m-%d")
    # Run PostgreSQL pg_dump command and capture output in memory
    dump_command = f"{pg_dump_path} -U {database_user} -d {database_name}"
    try:
        # Run the command and capture the output
        backup_output = subprocess.check_output(dump_command, shell=True)

        # Create an in-memory buffer and write the output to it
        in_memory_backup = io.BytesIO(backup_output)

        # Reset the pointer to the beginning of the in-memory file
        in_memory_backup.seek(0)

        # Upload the in-memory backup file to Linode Object Storage
        object_key = f"POSTGRES/postgres_{current_date}.sql"
        upload_to_linode_object_storage(in_memory_backup, object_key)
        remove_old_backups()
        return f"Database backup created and uploaded successfully: {object_key}"

    except subprocess.CalledProcessError as e:
        print(f"An error occurred during backup or upload: {e}")
        return f"An error occurred during backup or upload: {e}"

    # Connect to the IMAP server
    mail = imaplib.IMAP4_SSL("outlook.office365.com", 993)

    # Login to the server
    mail.login("hr@1553690ontarioinc.com", "qivjed-Cakqys-7jyvwy")

    # Select a mailbox (inbox, for example)
    mail.select("inbox")

    # Search for unseen emails
    result, data = mail.search(None, "UNSEEN")

    # Process retrieved emails
    for num in data[0].split():
        result, data = mail.fetch(num, "(RFC822)")
        email_data = data[0][1]  # Raw email content

        # Process email content here
        # Example: Print email subject
        print(email_data)

    # Close the connection
    mail.close()
    mail.logout()


@app.task(name="save_inciddent_file")
def save_incident_file(**kwargs):
    try:
        # Extract form data
        store_id = kwargs.pop("store", None)
        user_employer_id = kwargs.pop("user_employer", None)

        # Get the Store instance using the store_id
        store_instance = (
            Store.objects.get(pk=store_id) if store_id is not None else None
        )
        user_employer_instance = (
            Employer.objects.get(pk=user_employer_id)
            if user_employer_id is not None
            else None
        )

        # Set the Store instance back to the kwargs
        kwargs["store"] = store_instance
        kwargs["user_employer"] = user_employer_instance

        # Save the form data to the database
        incident = Incident.objects.create(**kwargs)

        return {
            "incident_store": incident.id,
            "Incident_brief": incident.brief_description,
            "message": "Incident Saved",
        }
    except Exception as e:
        logger.error(f"Error saving incident: {e}")
        return {"error": str(e)}


@app.task(name="save_user_to_db")
def save_user_to_db(**kwargs):
    try:
        # Create a new CustomUser object and save it to the database
        # Access the serialized data from kwargs
        employer_pk = kwargs.get("employer")
        manager_dropdown_pk = kwargs.get("manager_dropdown")
        dob_isoformat = kwargs.get("dob")
        manager_id = kwargs.get("manager_id")
        # Deserialize the data if needed
        # Convert employer_pk, manager_dropdown_pk, and dob_isoformat back to their original types
        # Perform the necessary processing with the data
        # Update UserManager with user and manager, etc.
        # Example:
        user = CustomUser.objects.get(pk=kwargs["user_id"])
        user.employer = Employer.objects.get(pk=employer_pk)
        user.manager = CustomUser.objects.get(pk=manager_dropdown_pk)
        user.dob = datetime.strptime(dob_isoformat, "%Y-%m-%d").date()
        user.save()
        # Create a new UserManager object to associate the user with the manager
        UserManager.objects.create(user=user, manager_id=manager_id)
    except Exception as e:
        # Handle any exceptions that may occur during database save
        print(f"An error occurred during database save: {e}")


@app.task(name="send_new_hire_quiz")
def send_new_hire_quiz(envelope_args):
    try:
        create_docusign_envelope_new_hire_quiz(envelope_args)
        signer_name = envelope_args.get("signer_name")
        logger.info(
            f"Docusign envelope New Hire Quiz for {signer_name} created successfully"
        )

        return f"Docusign envelope New Hire Quiz for {signer_name} created successfully"
    except Exception as e:
        logger.error(
            f"Error creating Docusign New Hire Quiz for {signer_name} envelope: {str(e)}"
        )
        return f"Error creating Docusign New Hire Quiz for {signer_name} envelope: {str(e)}"
