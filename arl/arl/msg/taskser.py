from celery import shared_task
from .helpers import send_sms

@shared_task
def send_sms_task(phone_number):
    send_sms(phone_number)