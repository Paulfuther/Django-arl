import base64
import json
import os
import traceback  # For detailed error reporting

from celery.utils.log import get_task_logger
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpResponse
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (Asm, Attachment, ContentId, Disposition,
                                   FileContent, FileName, FileType, Mail)
from twilio.base.exceptions import TwilioException
from twilio.rest import Client

from arl.msg.models import EmailTemplate
from arl.user.models import CustomUser, Store

from .models import EmailEvent  # Import your EmailEvent model

logger = get_task_logger(__name__)

account_sid = settings.TWILIO_ACCOUNT_SID
auth_token = settings.TWILIO_AUTH_TOKEN
twilio_from = settings.TWILIO_FROM
twilio_verify_sid = settings.TWILIO_VERIFY_SID
notify_service_sid = settings.TWILIO_NOTIFY_SERVICE_SID

client = Client(account_sid, auth_token)

sg = SendGridAPIClient(settings.SENDGRID_API_KEY)

# whatsapp message


# function to create an email using sendgrid and tempaltes


def create_tobacco_email(to_email, name):
    try:
        templatename = "Required Actions for Tobacco and Vape"
        bm = "d-488749fd81d4414ca7bbb2eea2b830db"
        message = Mail(from_email=settings.MAIL_DEFAULT_SENDER, to_emails=to_email)
        message.dynamic_template_data = {
            "subject": templatename,
            "name": name,
        }
        message.template_id = bm
        response = sg.send(message)

        # Handle the response and return an appropriate value based on your requirements
        if response.status_code != 202:
            logger.error(
                f"Failed to send email to {to_email}. Error code: {response.status_code}"
            )
    except Exception as e:
        error_message = f"An error occurred while sending email to {to_email}: {str(e)}"
        logger.error(error_message)

        if hasattr(e, "response") and e.response is not None:
            response_body = e.response.body
            response_status = e.response.status_code
            logger.error(f"SendGrid response status code: {response_status}")
            logger.error(f"SendGrid response body: {response_body}")

# this is the master email function


def create_master_email(to_email, name, sendgrid_id, attachments=None):
    try:
        unsubscribe_group_id = 24753
        # template = EmailTemplate.objects.get(id=template_id)

        # Initialize the email message
        message = Mail(
            from_email=settings.MAIL_DEFAULT_SENDER,
            to_emails=to_email,
        )

        # Add dynamic template data
        message.dynamic_template_data = {
            "name": name,
            "subject": "NONE",
        }
        message.template_id = sendgrid_id
        asm = Asm(
            group_id=unsubscribe_group_id,
        )
        message.asm = asm
        # Handle attachments if provided
        if attachments:
            for attachment in attachments:
                encoded_content = attachment.get("file_content")
                if encoded_content:
                    attachment_instance = Attachment(
                        FileContent(encoded_content),
                        FileName(attachment.get("file_name", "file")),
                        FileType(attachment.get("file_type", "application/octet-stream")),
                        Disposition("attachment")
                    )
                    message.attachment = attachment_instance

        # Send the email via SendGrid
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)

        # Check response status
        if response.status_code == 202:
            print(f"Email sent successfully to {to_email}.")
            return True
        else:
            print(f"Failed to send email to {to_email}. Status code: {response.status_code}")
            return False

    except Exception as e:
        # Extract detailed error information if available
        error_details = str(e)
        if hasattr(e, 'body'):
            error_details += f" Response body: {e.body}"

        # Log error details for debugging
        print(f"Error in create_master_email: {error_details}")
        traceback.print_exc()  # For detailed error trace
        return False


# for now we are going to keep this helper file
# it has data in the dynamic_template_date that is needed
# Eventually, we will merge this with master email.
def create_hr_newhire_email(**kwargs):
    CustomUser = get_user_model()

    # Get all active users in the 'hr' group
    hr_users = CustomUser.objects.filter(
        Q(is_active=True) & Q(groups__name="new_hire_data_email")
    )
    # Extract email addresses from the CustomUser objects
    to_emails = [user.email for user in hr_users]

    # Prepare Email
    message = Mail(
        from_email=settings.MAIL_DEFAULT_SENDER,
        to_emails=to_emails,
        subject="We have a New Employee",
    )
    message.dynamic_template_data = {
        "firstname": kwargs["firstname"],
        "lastname": kwargs["lastname"],
        "store": kwargs["store_number"],
        "storeaddress": kwargs["store_address"],
        "email": kwargs["email"],
        "mobilephone": kwargs["mobilephone"],
        "addressone": kwargs["addressone"],
        "addresstwo": kwargs["addresstwo"],
        "city": kwargs["city"],
        "province": kwargs["province"],
        "postal": kwargs["postal"],
        "country": kwargs["country"],
        "sin_number": kwargs["sin_number"],
        "dob": kwargs["dob"],
    }
    message.template_id = "d-d0806dff1e62449d9ba8cfcb481accaa"

    try:
        response = sg.send(message)

        # Handle the response and return an appropriate value based on your requirements
        if response.status_code == 202:
            return True
        else:
            print("Failed to send email. Error code:", response.status_code)
            return False

    except Exception as e:
        print("Error sending email:", e)
        return False


def create_single_email(to_email, name, template_id=None, attachments=None):
    """
    Create and send a single email using the SendGrid API.

    Args:
        to_email: The recipient's email address.
        name: The recipient's name for personalization.
        template_id: The SendGrid template ID (optional).
        attachments: List of attachments (optional).
            Each attachment is a dictionary with:
            {
                "file_content": file bytes content,
                "file_name": "example.pdf",
                "file_type": "application/pdf"
            }
    """
    unsubscribe_group_id = 24753
    message = Mail(
        from_email=settings.MAIL_DEFAULT_SENDER,
        to_emails=to_email,
    )
    message.dynamic_template_data = {
        "name": name,
    }
    message.template_id = template_id

    # Add ASM (Advanced Suppression Manager) for unsubscribe
    asm = Asm(
        group_id=unsubscribe_group_id,
        )
    message.asm = asm
    print(message)
    # Add attachments if provided
    if attachments:
        for attachment in attachments:
            encoded_file = base64.b64encode(attachment['file_content']).decode()

            attached_file = Attachment(
                FileContent(encoded_file),
                FileName(attachment['file_name']),
                FileType(attachment['file_type']),
                Disposition('attachment')
            )
            message.add_attachment(attached_file)

    try:
        response = sg.send(message)
        print(response.status_code)
        print(response.body)
        print(response.headers)
    except Exception as e:
        print(e.message)


def send_sms_model(phone_number, message):
    try:
        message = client.messages.create(
            body=message,
            from_=twilio_from,
            to=phone_number,
        )
        return message.sid
    except Exception as e:
        print("Failed to send SMS:", str(e))
    return None


def send_sms(phone_number, body):
    try:
        message = client.messages.create(
            body=body,
            from_=twilio_from,
            to=phone_number,
        )
        return message.sid
    except Exception as e:
        print("Failed to send SMS:", str(e))
    return None


def send_bulk_sms(numbers, body):
    try:
        # Your existing code

        bindings = list(
            map(
                lambda number: json.dumps({"binding_type": "sms", "address": number}),
                numbers,
            )
        )
        print("=====> To Bindings :>", bindings, "<: =====")
        notification = client.notify.services(
            settings.TWILIO_NOTIFY_SERVICE_SID
        ).notifications.create(to_binding=bindings, body=body)

        # Log a success message
        logger.info(f"Bulk SMS sent successfully to {', '.join(numbers)}")
        return True
    except Exception as e:
        # Log the exception
        logger.error(f"Failed to send bulk SMS: {str(e)}")
        return False


def _get_twilio_verify_client():
    return Client(account_sid, auth_token).verify.services(twilio_verify_sid)


def request_verification_token(phone):
    verify = _get_twilio_verify_client()
    try:
        verify.verifications.create(to=phone, channel="sms")
    except TwilioException:
        verify.verifications.create(to=phone, channel="call")


def check_verification_token(phone, token):
    verify = _get_twilio_verify_client()
    try:
        result = verify.verification_checks.create(to=phone, code=token)
    except TwilioException:
        return False
    return result.status == "approved"


def send_monthly_store_phonecall():
    client = Client(account_sid, auth_token)
    store_phone_numbers = Store.objects.values_list("phone_number", flat=True)
    for phone_number in store_phone_numbers:
        call = client.calls.create(
            to=phone_number,
            from_=settings.TWILIO_FROM,  # Replace with your Twilio phone number
            url="https://handler.twilio.com/twiml/EH559f02f8d84080226304bfd390b8ceb9",
        )

    return HttpResponse("Call initiated!")


def send_docusign_email_with_attachment(to_emails, subject, body, file_path):
    try:
        for to_email in to_emails:
            message = Mail(
                from_email=settings.MAIL_DEFAULT_SENDER,
                to_emails=to_email,
                subject=subject,
                html_content=body,
            )

            with open(file_path, "rb") as file:
                attachment_content = file.read()
                encoded_content = base64.b64encode(attachment_content).decode()

            attachment = Attachment()
            attachment.file_content = FileContent(encoded_content)
            attachment.file_name = FileName(file_path.split("/")[-1])
            attachment.file_type = FileType("application/zip")
            attachment.disposition = Disposition("attachment")
            attachment.content_id = ContentId("Attachment")

            message.attachment = attachment

            response = sg.send(message)
            if response.status_code == 202:
                print(f"Sent file by email to {to_email}", response.status_code)
            else:
                print(
                    f"Failed to send email to {to_email}. Error code:",
                    response.status_code,
                )

    except Exception as e:
        print("Error sending email:", str(e))


# sends a single email to the user with a pdf of
# the incident file attached.


def create_incident_file_email(
    to_email, subject, body, attachment_buffer=None, attachment_filename=None
):
    try:
        message = Mail(
            from_email=settings.MAIL_DEFAULT_SENDER,
            to_emails=to_email,
            subject=subject,
            html_content=body,
        )
        print(to_email)
        if attachment_buffer and attachment_filename:
            attachment = Attachment()
            attachment.file_content = FileContent(
                base64.b64encode(attachment_buffer.read()).decode()
            )
            attachment.file_name = FileName(attachment_filename)
            attachment.file_type = FileType("application/pdf")
            attachment.disposition = Disposition("attachment")
            attachment.content_id = ContentId("Attachment")

            message.attachment = attachment

        response = sg.send(message)

        if response.status_code != 202:
            print(
                "Failed to send email to", to_email, "Error code:", response.status_code
            )

    except Exception as e:
        error_message = f"An error occurred while sending email to {to_email}: {str(e)}"
        logger.error(error_message)

        if hasattr(e, "response") and e.response is not None:
            response_body = e.response.body
            response_status = e.response.status_code
            logger.error(f"SendGrid response status code: {response_status}")
            logger.error(f"SendGrid response body: {response_body}")


# sends new icident pdf to users with the rule
# incident_email


def create_incident_file_email_by_rule(
    to_emails, subject, body, attachment_buffer=None, attachment_filename=None
):
    try:
        for to_email in to_emails:
            message = Mail(
                from_email=settings.MAIL_DEFAULT_SENDER,
                to_emails=to_email,
                subject=subject,
                html_content=body,
            )
            print(to_email)
            if attachment_buffer and attachment_filename:
                attachment_buffer.seek(0)  
                # Ensure the buffer is at the beginning
                attachment_content = base64.b64encode(attachment_buffer.read()).decode()
                attachment = Attachment()
                attachment.file_content = FileContent(attachment_content)
                attachment.file_name = FileName(attachment_filename)
                attachment.file_type = FileType("application/pdf")
                attachment.disposition = Disposition("attachment")
                attachment.content_id = ContentId("Attachment")

                message.attachment = attachment

            response = sg.send(message)

            if response.status_code != 202:
                print(
                    "Failed to send email to",
                    to_email,
                    "Error code:",
                    response.status_code,
                )

    except Exception as e:
        error_message = f"An error occurred while sending email to {to_email}: {str(e)}"
        logger.error(error_message)

        if hasattr(e, "response") and e.response is not None:
            response_body = e.response.body
            response_status = e.response.status_code
            logger.error(f"SendGrid response status code: {response_status}")
            logger.error(f"SendGrid response body: {response_body}")


def send_incident_email(
    to_emails, subject, body, attachment_buffer=None, attachment_filename=None
):
    try:
        for to_email in to_emails:
            message = Mail(
                from_email=settings.MAIL_DEFAULT_SENDER,
                to_emails=to_email,
                subject=subject,
                html_content=body,
            )
            print(to_email)
            if attachment_buffer and attachment_filename:
                attachment_buffer.seek(0)  
                # Ensure the buffer is at the beginning
                attachment_content = base64.b64encode(attachment_buffer.read()).decode()
                attachment = Attachment()
                attachment.file_content = FileContent(attachment_content)
                attachment.file_name = FileName(attachment_filename)
                attachment.file_type = FileType("application/pdf")
                attachment.disposition = Disposition("attachment")
                attachment.content_id = ContentId("Attachment")

                message.attachment = attachment

            response = sg.send(message)

            if response.status_code != 202:
                print(
                    "Failed to send email to",
                    to_email,
                    "Error code:",
                    response.status_code,
                )

    except Exception as e:
        error_message = f"An error occurred while sending email to {to_email}: {str(e)}"
        logger.error(error_message)

        if hasattr(e, "response") and e.response is not None:
            response_body = e.response.body
            response_status = e.response.status_code
            logger.error(f"SendGrid response status code: {response_status}")
            logger.error(f"SendGrid response body: {response_body}")



def send_whats_app_template(content_sid, from_sid, user_name, to_number):
    # Ensure phone number is in the correct format
    whatsapp_number = f"whatsapp:+{to_number}"
    # Properly format the content variables for the template
    content_vars = json.dumps({"1": user_name})
    # Log the variables to debug or verify; consider reducing logging in production
    print(f"Sending to {whatsapp_number} with name {user_name}")

    try:
        # Create the message
        message = client.messages.create(
            content_sid=content_sid,
            from_=from_sid,
            content_variables=content_vars,
            to=whatsapp_number,
        )
        # print(f"Message sent with SID: {message.sid}")
        return message.sid
    except Exception as e:
        # Handle errors in message sending
        print(f"Failed to send message: {str(e)}")
        return None


def send_whats_app_carwash_sites_template(content_sid, from_sid, user_name, 
                                          to_number, content_vars):
    # Ensure phone number is in the correct format
    whatsapp_number = f"whatsapp:+{to_number}"
    # Properly format the content variables for the template
    # content_vars = json.dumps({"1": user_name})
    # Log the variables to debug or verify; consider reducing logging in production
    print(f"Sending to {whatsapp_number} with name {user_name}")

    try:
        # Create the message
        message = client.messages.create(
            content_sid=content_sid,
            from_=from_sid,
            content_variables=content_vars,
            to=whatsapp_number,
        )
        # print(f"Message sent with SID: {message.sid}")
        return message.sid
    except Exception as e:
        # Handle errors in message sending
        print(f"Failed to send message: {str(e)}")
        return None


def create_single_csv_email(to_email, subject, body, file_path):
    message = Mail(
        from_email=settings.MAIL_DEFAULT_SENDER,
        to_emails=[to_email],
        subject=subject,
        html_content=body,
    )
    if file_path:
        with open(file_path, "rb") as f:
            data = f.read()
            encoded = base64.b64encode(data).decode()

        attachment = Attachment()
        attachment.file_content = FileContent(encoded)
        attachment.file_name = FileName(os.path.basename(file_path))
        attachment.file_type = FileType("text/csv")
        attachment.disposition = Disposition("attachment")
        attachment.content_id = ContentId("CSV Attachment")
        message.attachment = attachment

    response = sg.send(message)
    if response.status_code == 202:
        return True
    else:
        print("Failed to send email. Status code:", response.status_code)
        return False


def send_whats_app_template_autoreply(content_sid, from_sid, to_number):
    # Ensure phone number is in the correct format
    whatsapp_number = f"whatsapp:+{to_number}"
    # Log the variables to debug or verify; consider reducing logging in production
    print(f"Sending to {whatsapp_number} autoreply")

    try:
        # Create the message
        message = client.messages.create(
            content_sid=content_sid,
            from_=from_sid,
            to=whatsapp_number,
        )
        # print(f"Message sent with SID: {message.sid}")
        return message.sid
    except Exception as e:
        # Handle errors in message sending
        print(f"Failed to send message: {str(e)}")
        return None


def get_inactive_contact_ids():
    """Retrieve contact IDs of inactive users from SendGrid based on email."""
    inactive_emails = CustomUser.objects.filter(is_active=False).values_list('email', flat=True)
    inactive_emails = [email for email in inactive_emails if email]  # Filter out empty emails
    contact_ids = []

    for email in inactive_emails:
        response = sg.client.marketing.contacts.search.post(
            request_body={"query": f"email LIKE '{email}'"}
        )
        data = json.loads(response.body)  # Convert the response to JSON (dictionary)
        if 'result' in data and len(data['result']) > 0:
            contact_ids.append(data['result'][0]['id'])

    print("Contact IDs for deletion:", contact_ids)  # Debugging print
    return contact_ids


def delete_contacts_by_ids(contact_ids):
    """Delete contacts from SendGrid using their contact IDs."""
    if contact_ids:
        ids_string = ','.join(contact_ids)
        try:
            delete_response = sg.client.marketing.contacts.delete(
                query_params={"ids": ids_string}
            )
            print("Deletion response:", delete_response.status_code, delete_response.body)
        except Exception as e:
            print("Deletion error:", e)
    else:
        print("No inactive contact IDs to delete.")


def add_active_contacts(selected_list_id):
    """Add active users to SendGrid with first name, last name, and email."""
    # Retrieve active users with first name, last name, and email
    active_users = CustomUser.objects.filter(is_active=True).values('email', 'first_name', 'last_name')
    contacts = [
        {
            "email": user['email'],
            "first_name": user['first_name'],
            "last_name": user['last_name']
        }
        for user in active_users if user['email']  # Ensure no empty emails
    ]
    print(contacts)
    if contacts:
        data = {
            "list_ids": [selected_list_id],  # Specify the target list ID
            "contacts": contacts
        }
        try:
            add_response = sg.client.marketing.contacts.put(request_body=data)
            print("Addition response:", add_response.status_code, add_response.body)
        except Exception as e:
            print("Addition error:", e)


def sync_contacts_with_sendgrid(selected_list_id):
    """Main function to sync contacts with SendGrid: remove inactive contacts, add active ones."""
    contact_ids = get_inactive_contact_ids()
    delete_contacts_by_ids(contact_ids)
    add_active_contacts(selected_list_id)


def get_all_contact_lists():
    """Retrieve all contact lists and their IDs from SendGrid."""
    try:
        response = sg.client.marketing.lists.get()
        lists = response.to_dict.get('result', [])
        for contact_list in lists:
            print(f"List Name: {contact_list['name']}, List ID: {contact_list['id']}")
        return lists
    except Exception as e:
        print("Error retrieving contact lists:", e)
