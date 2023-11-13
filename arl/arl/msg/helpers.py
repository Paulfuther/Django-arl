import base64
import json

from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
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
        message = Mail(from_email=settings.MAIL_DEFAULT_SENDER, to_emails=to_email)
        message.dynamic_template_data = {
            "subject": templatename,
            "name": name,
        }
        message.template_id = "d-488749fd81d4414ca7bbb2eea2b830db"
        response = sg.send(message)

        # Handle the response and return an appropriate value based on your requirements
        if response.status_code != 202:
            logger.error(
                f"Failed to send email to {to_email}. Error code: {response.status_code}"
            )
    except Exception as e:
        logger.error(f"An error occurred while sending email to {to_email}: {str(e)}")


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
    message = Mail(
        from_email=settings.MAIL_DEFAULT_SENDER,
        to_emails=["paul.futher@gmail.com", "hr1553690@yahoo.com"],
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
    response = sg.send(message)

    # Handle the response and return an appropriate value based on your requirements
    if response.status_code == 202:
        return True
    else:
        print("Failed to send email. Error code:", response.status_code)
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


def send_sms(phone_number):
    try:
        message = client.messages.create(
            body="Hello from me, dude! Its Sunday again",
            from_=twilio_from,
            to=phone_number,
        )
        return message.sid
    except Exception as e:
        print("Failed to send SMS:", str(e))
    return None


def create_bulk_sms():
    numbers = ["+15196707469"]
    body = "hello crazy people. Its time."
    bindings = list(
        map(
            lambda number: json.dumps({"binding_type": "sms", "address": number}),
            numbers,
        )
    )
    print("=====> To Bindings :>", bindings, "<: =====")
    notification = client.notify.services(notify_service_sid).notifications.create(
        to_binding=bindings, body=body
    )
    return HttpResponse("Bulk SMS sent successfully.")  # or redirect to a success page


def send_bulk_sms(numbers, body):
    bindings = list(
        map(
            lambda number: json.dumps({"binding_type": "sms", "address": number}),
            numbers,
        )
    )
    print("=====> To Bindings :>", bindings, "<: =====")
    notification = client.notify.services(notify_service_sid).notifications.create(
        to_binding=bindings, body=body
    )


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
