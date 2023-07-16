from __future__ import absolute_import, unicode_literals

import json

from arl.celery import app
from arl.msg.helpers import (client, create_email,
                             notify_service_sid, send_sms)


@app.task(name='add')
def add(x, y):
    return x + y


@app.task(name='sms')
def send_sms_task(phone_number):
    return send_sms(phone_number)


@app.task(name='send_email')
def send_template_email_task(to_email, subject, name, template_id):
    return create_email(to_email, subject, name, template_id)


@app.task(name='bulk_sms')
def send_bulk_sms_task():
    numbers = ['+15196707469']
    body = 'hello crazy people. Its time.'
    bindings = list(map(lambda number:
                        json.dumps({"binding_type": "sms", "address": number}), numbers))
    print("=====> To Bindings :>", bindings, "<: =====")
    notification = client.notify.services(notify_service_sid).notifications.create(
            to_binding=bindings,
            body=body)
    return 'Bulk SMS sent successfully.'  # or redirect to a success page
