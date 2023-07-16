from __future__ import absolute_import, unicode_literals

from arl.celery import app

from arl.msg.helpers import send_sms


@app.task(name='add')
def add(x, y):
    return x + y


@app.task(name='sms')
def send_sms_task(phone_number):
    send_sms(phone_number)
