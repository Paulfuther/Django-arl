from __future__ import absolute_import, unicode_literals

import logging
from io import BytesIO

import pdfkit
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils.text import slugify

from arl.celery import app
from arl.dbox.helpers import upload_major_incident_file_to_dropbox
from arl.helpers import (get_s3_images_for_incident,
                         upload_to_linode_object_storage)
from arl.msg.helpers import (create_incident_file_email,
                             create_incident_file_email_by_rule)
from arl.user.models import CustomUser, Employer, Store

from .models import MajorIncident

logger = logging.getLogger(__name__)


# Once a new Major Incident File has been submitted
# we call this task to save the data to the database.
# This takes some load off of the server.
# Then we call a signal to send the emails.

@app.task(name="save_major_inciddent_file")
def save_major_incident_file(**kwargs):
    try:
        # Extract form data
        store_id = kwargs.pop("store", None)
        user_employer_id = kwargs.pop("user_employer", None)

        # Get the Store instance using the store_id
        store_instance = (
            Store.objects.get(pk=store_id) if store_id is not None else None
        )
        user_employer_instance = (
            Employer.objects.get(pk=user_employer_id)
            if user_employer_id is not None
            else None
        )

        # Set the Store instance back to the kwargs
        kwargs["store"] = store_instance
        kwargs["user_employer"] = user_employer_instance

        # Save the form data to the database
        incident = MajorIncident.objects.create(**kwargs)

        return {
            "incident_store": incident.id,
            "Incident_brief": incident.brief_description,
            "message": "Incident Saved",
        }
    except Exception as e:
        logger.error(f"Error saving incident: {e}")
        return {"error": str(e)}

# This route takes the newly created Major Incident
# and sends out a copy to the appropriate emails
# and uploads it to dropbox.


@app.task(name="create_major_incident_pdf")
def generate_major_incident_pdf_task(incident_id):
    try:
        # Fetch incident data based on incident_id
        try:
            incident = MajorIncident.objects.get(pk=incident_id)
        except ObjectDoesNotExist:
            raise ValueError("Incident with ID {} does not exist.".
                             format(incident_id))

        images = get_s3_images_for_incident(
            incident.image_folder, incident.user_employer
        )
        context = {"incident": incident, "images": images}
        html_content = render_to_string(
            "incident/major_incident_form_pdf.html", context)
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
        store_number = incident.store.number  # Replace with your actual
        # attribute name
        brief_description = incident.brief_description
        # Create a unique file name for the PDF using store number and brief
        # description
        pdf_filename = (
            f"{store_number}_{slugify(brief_description)}"
            f"_report.pdf"
        )

        # Close the BytesIO buffer to free up resources
        # Set the BytesIO buffer's position to the beginning
        # Upload the PDF to Linode Object Storage
        object_key = (
            f"MAJORSITEINCIDENT/{incident.user_employer}/MAJORINCIDENTPDF/"
            f"{pdf_filename}"
        )
        upload_to_linode_object_storage(pdf_buffer, object_key)

        # Upload the PDF to Dropbox
        upload_major_incident_file_to_dropbox(pdf, pdf_filename)
        # Set the BytesIO buffer's position to the beginning
        pdf_buffer.seek(0)

        # Close the BytesIO buffer to free up resources
        # Then email to the current user and all users in
        # the group incident_form_email

        subject = "A New Major Incident Report Has Been Created"
        body = (
            "Thank you for using our services. Attached "
            "is your incident report."
        )
        # attachment_data = pdf_buffer.getvalue()

        # Call the create_incident_file_email_by_rule
        # user_email and other details

        to_emails = CustomUser.objects.filter(
            Q(is_active=True) & Q(groups__name="major_incident_form_email")
        ).values_list("email", flat=True)

        create_incident_file_email_by_rule(
            to_emails, subject, body, pdf_buffer, pdf_filename
        )

        return {
            "status": "success",
            "message": "PDF generated and uploaded successfully",
        }
    except Exception as e:
        logger.error("Error in generate_pdf_task: {}".format(e))
        return {"status": "error", "message": str(e)}


@app.task(name="create_major_incident_pdf_from_list")
def generate_major_incident_pdf_from_list_task(incident_id, user_email):
    try:
        # Fetch incident data based on incident_id
        try:
            incident = MajorIncident.objects.get(pk=incident_id)
        except ObjectDoesNotExist:
            raise ValueError(
                "Incident with ID {} does not exist.".format(incident_id)
            )

        # get images, if there are any, from the s3 bucket
        images = get_s3_images_for_incident(
            incident.image_folder, incident.user_employer
        )
        context = {"incident": incident, "images": images}
        html_content = render_to_string(
            "incident/major_incident_form_pdf.html", context
            )
        #  Generate the PDF using pdfkit
        options = {
            "enable-local-file-access": None,
            "--keep-relative-links": "",
            "encoding": "UTF-8",
        }
        # create the pdf
        pdf = pdfkit.from_string(html_content, False, options)
        #  Create a BytesIO object to store the PDF content
        pdf_buffer = BytesIO(pdf)
        # Create a unique file name for the PDF
        store_number = incident.store.number
        # Replace with your actual attribute name
        brief_description = incident.brief_description
        # Create a unique file name for the PDF
        # using store number and brief description
        pdf_filename = (
            f"{store_number}_{slugify(brief_description)}"
            f"_report.pdf"
        )

        # Close the BytesIO buffer to free up resources
        # Then email to the current user

        subject = f"Your Incident Report {pdf_filename}"
        body = "Thank you for using our services. "
        "Attached is your incident report."
        # attachment_data = pdf_buffer.getvalue()

        # Call the create_single_email function with
        # user_email and other details
        create_incident_file_email(user_email, subject, body,
                                   pdf_buffer, pdf_filename)
        # create_single_email(user_email, subject, body, pdf_buffer)

        return {
            "status": "success",
            "message": f"Incident {pdf_filename} emailed to {user_email}",
        }
    except Exception as e:
        logger.error("Error in generate_pdf_task: {}".format(e))
        return {"status": "error", "message": str(e)}
