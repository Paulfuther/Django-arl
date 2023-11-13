from __future__ import absolute_import, unicode_literals

import json
from io import BytesIO

import pdfkit
from celery.exceptions import SoftTimeLimitExceeded
from celery.utils.log import get_task_logger
from django.template.loader import render_to_string
from django.utils.text import slugify

from arl.celery import app
from arl.dsign.helpers import create_docusign_envelope
from arl.helpers import get_s3_images_for_incident, upload_to_linode_object_storage
from arl.incident.models import Incident
from arl.msg.helpers import (
    client,
    create_email,
    create_hr_newhire_email,
    create_single_email,
    create_tobacco_email,
    notify_service_sid,
    send_monthly_store_phonecall,
    send_sms,
    send_sms_model,
)
from arl.user.models import CustomUser, Store

logger = get_task_logger(__name__)


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


@app.task(name="send_weekly_tobacco_email")
def send_weekly_tobacco_email():
    try:
        active_users = CustomUser.objects.filter(is_active=True)
        for user in active_users:
            create_tobacco_email(user.email, user.username)
        return "Tobacco Emails Sent Successfully"
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return f"Failed to send tobacco emails. Error: {str(e)}"


@app.task(name="send_template_email")
def send_template_email_task(to_email, subject, name, template_id):
    try:
        create_email(to_email, subject, name, template_id)
        return "Template Email Sent Successfully"
    except Exception as e:
        return str(e)


@app.task(name="send_email")
def send_email_task(to_email, subject, name):
    try:
        create_single_email(to_email, subject, name)
        return "Email Sent Successfully"
    except Exception as e:
        return str(e)


@app.task(name="bulk_sms")
def send_bulk_sms_task():
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
    return "Bulk SMS sent successfully."  # or redirect to a success page


@app.task(name="monthly_store_calls")
def monthly_store_calls_task():
    send_monthly_store_phonecall()


@app.task(name="create_incident_pdf")
def generate_pdf_task(incident_id, user_email):
    try:
        #  Fetch incident data based on incident_id
        incident = Incident.objects.get(pk=incident_id)  # Get the incident
        # user = incident.user
        images = get_s3_images_for_incident(
            incident.image_folder, incident.user_employer
        )
        # print(images)
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
        brief_description = (
            incident.brief_description
        )  # Replace with your actual attribute name
        # Create a unique file name for the PDF using store number and brief description
        pdf_filename = f"{store_number}_{slugify(brief_description)}_report.pdf"
        # Save the PDF to a temporary location
        # with open(pdf_filename, "wb") as pdf_file:
        #    pdf_file.write(pdf_buffer.getvalue())
        # Close the BytesIO buffer to free up resources
        #  Set the BytesIO buffer's position to the beginning
        # Upload the PDF to Linode Object Storage
        object_key = f"SITEINCIDENT/{incident.user_employer}/INCIDENTPDF/{pdf_filename}"
        upload_to_linode_object_storage(pdf_buffer, object_key)
        pdf_buffer.seek(0)
        #  Close the BytesIO buffer to free up resources
        subject = "Your Incident Report"
        body = "Thank you for using our services. Attached is your incident report."
        attachment_data = pdf_buffer.getvalue()

        # Call the create_single_email function with user_email and other details
        create_single_email(user_email, subject, body, pdf_buffer, pdf_filename)
        # create_single_email(user_email, subject, body, pdf_buffer)

        return {
            "status": "success",
            "message": "PDF generated and uploaded successfully",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.task(name="create_docusign_envelope")
def create_docusign_envelope_task(envelope_args):
    create_docusign_envelope(envelope_args)


@app.task(name="create_hr_newhire_email")
def create_newhiredata_email(**kwargs):
    create_hr_newhire_email(**kwargs)
