import json

from django.conf import settings
from django.http import HttpResponse
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from twilio.base.exceptions import TwilioException
from twilio.rest import Client
from django.core.mail.backends.base import BaseEmailBackend

account_sid = settings.TWILIO_ACCOUNT_SID
auth_token = settings.TWILIO_AUTH_TOKEN
twilio_from = settings.TWILIO_FROM
twilio_verify_sid = settings.TWILIO_VERIFY_SID
notify_service_sid = settings.TWILIO_NOTIFY_SERVICE_SID

client = Client(account_sid, auth_token)

sg = SendGridAPIClient(settings.SENDGRID_API_KEY)

# function to create an email using sendgrid and tempaltes


def create_tobacco_email(to_email, subject, name, template_id):
    subject = subject
    message = Mail(
        from_email=settings.MAIL_DEFAULT_SENDER,
        to_emails=to_email)
    message.dynamic_template_data = {
        'subject': subject,
        'name': name,
        }
    message.template_id = template_id
    response = sg.send(message)

    # Handle the response and return an appropriate value based on your requirements
    if response.status_code == 202:
        return True
    else:
        print("Failed to send email. Error code:", response.status_code)
        return False

def create_email(to_email, subject, name, template_id):
    subject = subject
    message = Mail(
        from_email=settings.MAIL_DEFAULT_SENDER,
        to_emails=to_email)
    message.dynamic_template_data = {
        'subject': subject,
        'name': name,
        }
    message.template_id = template_id
    response = sg.send(message)

    # Handle the response and return an appropriate value based on your requirements
    if response.status_code == 202:
        return True
    else:
        print("Failed to send email. Error code:", response.status_code)
        return False

def create_single_email(to_email, subject, body):
    subject = subject
    message = Mail(
        from_email=settings.MAIL_DEFAULT_SENDER,
        to_emails=to_email,
        subject=subject,
        html_content=body)
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
                body='Hello from me, dude! Its Sunday again',
                from_=twilio_from,
                to=phone_number,
            )
        return message.sid
    except Exception as e:
        print("Failed to send SMS:", str(e))
    return None


def create_bulk_sms():
    numbers = ['+15196707469']
    body = 'hello crazy people. Its time.'
    bindings = list(map(lambda number:
                        json.dumps({"binding_type": "sms", "address": number}), numbers))
    print("=====> To Bindings :>", bindings, "<: =====")
    notification = client.notify.services(notify_service_sid).notifications.create(
            to_binding=bindings,
            body=body)
    return HttpResponse('Bulk SMS sent successfully.')  # or redirect to a success page

def send_bulk_sms(numbers, body):
    bindings = list(map(lambda number: json.dumps({"binding_type":"sms","address": number}), numbers))
    print("=====> To Bindings :>", bindings, "<: =====")
    notification = client.notify.services(notify_service_sid)\
        .notifications.create(
            to_binding=bindings,
        body=body)



def _get_twilio_verify_client():
    return Client(account_sid, auth_token).verify.services(twilio_verify_sid)


def request_verification_token(phone):
    verify = _get_twilio_verify_client()
    try:
        verify.verifications.create(to=phone, channel='sms')
    except TwilioException:
        verify.verifications.create(to=phone, channel='call')


def check_verification_token(phone, token):
    verify = _get_twilio_verify_client()
    try:
        result = verify.verification_checks.create(to=phone, code=token)
    except TwilioException:
        return False
    return result.status == 'approved'

