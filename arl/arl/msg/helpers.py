import json
import os

from django.http import HttpResponse, request, JsonResponse
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from twilio.rest import Client
from twilio.base.exceptions import TwilioException

account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
twilio_from = os.environ.get('TWILIO_FROM')
twilio_verify_sid = os.environ.get('TWILIO_VERIFY_SID')
notify_service_sid = os.environ.get('TWILIO_NOTIFY_SERVICE_SID')

client = Client(account_sid, auth_token)

sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))

# function to create an email using sendgrid and tempaltes


def create_email(to_email, subject, name=None, template_id=None):
    subject = subject
    message = Mail(
        from_email=os.environ.get('MAIL_DEFAULT_SENDER'),
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


def send_sms(phone_number):
    try:
        message = client.messages.create(
                body='Hello from me, dude!',
                from_=twilio_from,
                to=phone_number,
            )
        return message.sid
    except Exception as e:
        print("Failed to send SMS:", str(e))
    return None


def create_bulk_sms(request):
    numbers = ['+15196707469', '+12267730404']
    body = 'hello crazy people. Its time.',
    bindings = list(map(lambda number:
                        json.dumps({"binding_type": "sms", "address": number}), numbers))
    print("=====> To Bindings :>", bindings, "<: =====")
    notification = client.notify.services(notify_service_sid).notifications.create(
            to_binding=bindings,
            body=body)
    return HttpResponse('Bulk SMS sent successfully.')  # or redirect to a success page
   

def _get_twilio_verify_client():
    return Client(account_sid, auth_token).verify.services(twilio_verify_sid)


def request_verification_token(phone):
    verify = _get_twilio_verify_client()
    try:
        verify.verifications.create(to=phone, channel='sms')
    except TwilioException:
        verify.verifications.create(to=phone, channel='call')


def check_verification_token(request):
    if request.method == 'POST':
        phone = request.POST.get('phone_number')
        token = request.POST.get('verification_code')
        print('Phone number:', phone)
        print('Verification code:', token)
        print(phone, token)
        verify = _get_twilio_verify_client()
        result = verify.verification_checks.create(to=phone, code=token)
        if result:
            # Verification successful
            print("pass")
            return JsonResponse({'success': True})
        else:
            # Verification failed
            print("faile")
            return JsonResponse({'success': False, 'error': 'Invalid verification code'})

    # Return an error response for unsupported request methods
    return JsonResponse({'success': False, 'error': 'Invalid request method'})
