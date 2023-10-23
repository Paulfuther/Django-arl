from __future__ import absolute_import, unicode_literals

import json
import os
from io import BytesIO

import pdfkit
from django.http import HttpResponse
from django.template.loader import render_to_string

from arl.celery import app
from arl.helpers import get_s3_images_for_incident
from arl.incident.models import Incident
from arl.msg.helpers import client, create_email, notify_service_sid, send_sms, send_sms_model
from arl.user.models import Store


@app.task(name="add")
def add(x, y):
    return x + y


@app.task(name="sms")
def send_sms_task(phone_number, message):
    try:
        send_sms_model(phone_number, message)
        return "Message sent successfully"
    except Exception as e:
        return str(e)
    # return send_sms(phone_number)


@app.task(name="send_email")
def send_template_email_task(to_email, subject, name, template_id):
    return create_email(to_email, subject, name, template_id)


@app.task(name="bulk_sms")
def send_bulk_sms_task():
    numbers = ["+15196707469"]
    body = "hello crazy people. Its time."
    bindings = list(
        map(lambda number: json.dumps({"binding_type": "sms", "address": number}), numbers)
    )
    print("=====> To Bindings :>", bindings, "<: =====")
    notification = client.notify.services(notify_service_sid).notifications.create(
        to_binding=bindings, body=body
    )
    return "Bulk SMS sent successfully."  # or redirect to a success page


@app.task(name="monthly_store_calls")
def monthly_store_calls_task():
    twimlid = "https://handler.twilio.com/twiml/EH559f02f8d84080226304bfd390b8ceb9"
    twilio_from = os.environ.get("TWILIO_FROM")
    # this is using twilml machine learning text to speach.
    # this only goes out to stores.
    stores = Store.objects.all()
    phone_numbers = [store.phone_number for store in stores]
    for phone_number in phone_numbers:
        call = client.calls.create(url=twimlid, to=phone_number, from_=twilio_from)


@app.task(name="create_incident_pdf")
def create_incident_pdf(incident_id):
    user = request.user
    #  Fetch incident data based on incident_id
    incident = Incident.objects.get(pk=incident_id)  # Get the incident
    images = get_s3_images_for_incident(incident.image_folder, user.employer)
    context = {"incident": incident, "images": images}  # Add more context as needed
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

    #  Set the BytesIO buffer's position to the beginning
    pdf_buffer.seek(0)

    #  Create an HTTP response with PDF content
    response = HttpResponse(pdf_buffer.read(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="incident_report.pdf"'

    #  Close the BytesIO buffer to free up resources
    pdf_buffer.close()

    return response
