import base64
import json

from celery.utils.log import get_task_logger
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpResponse
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Attachment,
    ContentId,
    Disposition,
    FileContent,
    FileName,
    FileType,
    Mail,
)
from twilio.base.exceptions import TwilioException
from twilio.rest import Client

from arl.user.models import Store

logger = get_task_logger(__name__)

account_sid = settings.TWILIO_ACCOUNT_SID
auth_token = settings.TWILIO_AUTH_TOKEN
twilio_from = settings.TWILIO_FROM
twilio_verify_sid = settings.TWILIO_VERIFY_SID
notify_service_sid = settings.TWILIO_NOTIFY_SERVICE_SID

client = Client(account_sid, auth_token)

sg = SendGridAPIClient(settings.SENDGRID_API_KEY)

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


def create_email(to_email, subject, name, template_id):
    subject = subject
    message = Mail(from_email=settings.MAIL_DEFAULT_SENDER, to_emails=to_email)
    message.dynamic_template_data = {
        "subject": subject,
        "name": name,
    }
    message.template_id = template_id
    response = sg.send(message)

    # Handle the response and return an appropriate value based on your requirements
    if response.status_code == 202:
        return True
    else:
        print("Failed to send email. Error code:", response.status_code)
        return False


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


def create_single_email(
    to_email, subject, body, attachment_buffer=None, attachment_filename=None
):
    subject = subject
    message = Mail(
        from_email=settings.MAIL_DEFAULT_SENDER,
        to_emails=to_email,
        subject=subject,
        html_content=body,
    )
    if attachment_buffer and attachment_filename:
        # Create an attachment
        attachment = Attachment()
        attachment.file_content = FileContent(
            base64.b64encode(attachment_buffer.read()).decode()
        )
        attachment.file_name = FileName(attachment_filename)
        attachment.file_type = FileType("application/pdf")
        attachment.disposition = Disposition("attachment")
        attachment.content_id = ContentId("Attachment")

        # Add the attachment to the message
        message.attachment = attachment

    response = sg.send(message)
    # Handle the response and return an appropriate value based on your requirements
    if response.status_code == 202:
        return True
    else:
        print("Failed to send email. Error code:", response.status_code)
        return False


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


def create_incident_file_email(to_email, subject, body, attachment_buffer=None, attachment_filename=None):
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
            print("Failed to send email to", to_email, "Error code:", response.status_code)

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


def create_incident_file_email_by_rule(to_emails, subject, body, attachment_buffer=None, attachment_filename=None):
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
                attachment_buffer.seek(0)  # Ensure the buffer is at the beginning
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
                print("Failed to send email to", to_email, "Error code:", response.status_code)

    except Exception as e:
        error_message = f"An error occurred while sending email to {to_email}: {str(e)}"
        logger.error(error_message)

        if hasattr(e, "response") and e.response is not None:
            response_body = e.response.body
            response_status = e.response.status_code
            logger.error(f"SendGrid response status code: {response_status}")
            logger.error(f"SendGrid response body: {response_body}")
