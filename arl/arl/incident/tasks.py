from __future__ import absolute_import, unicode_literals

import logging
from io import BytesIO

import pdfkit
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify

from arl.celery import app
from arl.dbox.helpers import (master_upload_file_to_dropbox,
                              upload_major_incident_file_to_dropbox)
from arl.helpers import (get_s3_images_for_incident,
                         upload_to_linode_object_storage)
from arl.msg.helpers import (create_incident_file_email,
                             create_incident_file_email_by_rule,
                             send_incident_email)
from arl.user.models import CustomUser, Employer, Store, ExternalRecipient

from .helpers import create_pdf
from .models import Incident, MajorIncident

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

        subject = f"Your Major Incident Report {pdf_filename}"
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


@app.task(name="save_inciddent_file")
def save_incident_file(**kwargs):
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
        incident = Incident.objects.create(**kwargs)

        return {
            "incident_store": incident.id,
            "Incident_brief": incident.brief_description,
            "message": "Incident Saved",
        }
    except Exception as e:
        logger.error(f"Error saving incident: {e}")
        return {"error": str(e)}


# This task is used when a site incident form is first created.
# There are four tasks to be called.
# generate_pdf_task_upload_to_linode_task, upload_to_dropbox_task
# and send_email_to_group_task

@app.task(name="create_incident_pdf")
def generate_pdf_task(incident_id):
    '''
    This task is used to create a pdf of a site incident form.
    '''
    try:
        pdf_result = create_pdf(incident_id)

        if pdf_result["status"] != "success":
            raise Exception(f"Failed to generate PDF: {pdf_result['message']}")

        # Return the PDF details for further tasks
        return {
            "pdf_filename": pdf_result["pdf_filename"],
            "pdf_buffer": pdf_result["pdf_buffer"].getvalue(),
            "incident_id": incident_id,
        }
    except Exception as e:
        raise Exception(f"Error in generate_pdf_task: {e}")


@app.task(name="upload_incident_pdf_to_linode")
def upload_to_linode_task(data):
    """
    Task to upload the generated PDF to Linode Object Storage.
    """
    try:
        pdf_data = data["pdf_buffer"]
        pdf_filename = data["pdf_filename"]
        incident_id = data["incident_id"]
        # Convert bytes back to a BytesIO object
        pdf_buffer = BytesIO(pdf_data)
        # Upload to Linode Object Storage
        user_employer = Incident.objects.get(pk=incident_id).user_employer
        object_key = (
            f"SITEINCIDENT/{user_employer}/INCIDENTPDF/{pdf_filename}"
        )
        upload_to_linode_object_storage(pdf_buffer, object_key)
        # Update and return the data dictionary
        data["object_key"] = object_key
        return data
    except Exception as e:
        raise Exception(f"Error in upload_to_storage_task: {e}")


@app.task(name="upload_incident_pdf_to_dropbox")
def upload_file_to_dropbox_task(data):
    """
    Task to upload a file to Dropbox using the provided file content and path.
    """
    try:
        # Extract data
        pdf_data = data["pdf_buffer"]
        pdf_filename = data["pdf_filename"]
        # incident_id = data["incident_id"]

        # Construct the Dropbox file path
        # user_employer = Incident.objects.get(pk=incident_id).user_employer
        dropbox_file_path = f"/SITEINCIDENT/{pdf_filename}"

        # Call the helper function to upload the file
        success, message = master_upload_file_to_dropbox(pdf_data,
                                                         dropbox_file_path)

        if not success:
            # Check for specific error cases
            if "insufficient_space" in message:
                logger.error("Dropbox upload failed: Dropbox is full.")
                return {"status": "failure", "message": "Dropbox is full. Please free up some space."}
            else:
                raise Exception(f"Dropbox upload failed: {message}")

        # Return updated data for the next task
        data["dropbox_path"] = dropbox_file_path
        return data

    except KeyError as e:
        error_message = f"Missing key in data passed to upload_file_to_dropbox_task: {e}"
        logger.error(error_message)
        raise Exception(error_message)

    except Exception as e:
        # Log and raise other unexpected errors
        error_message = f"Error in upload_file_to_dropbox_task: {e}"
        logger.error(error_message)
        raise Exception(error_message)


@app.task(name="email_incident_pdf_to_group")
def send_email_to_group_task(data, group_name, subject):
    try:
        # Fetch the emails of active users in the specified group
        to_emails = CustomUser.objects.filter(
            Q(is_active=True) & Q(groups__name=group_name)
        ).values_list("email", flat=True)

        if not to_emails:
            raise ValueError(f"No active users found in group: {group_name}")

        # Convert the PDF bytes back to BytesIO for attachment
        pdf_buffer = BytesIO(data["pdf_buffer"])
        pdf_filename = data["pdf_filename"]

        # Send the email with the PDF attachment
        create_incident_file_email_by_rule(
            to_emails=to_emails,
            subject=subject,
            body=(
                "Thank you for using our services. "
                "Attached is your incident report."
            ),
            attachment_buffer=pdf_buffer,
            attachment_filename=pdf_filename,
        )

        return {
            "status": "success",
            "message": f"Emails sent to group '{group_name}' successfully.",
        }
    except Exception as e:
        logger.error(f"Error sending email to group '{group_name}': {e}")
        return {"status": "error", "message": str(e)}


# This task creates a pdf of the select Incident Form
# Then emails the form to the user.
# This is called from the list of incidents
# when you click the pdf button


@app.task(name="email_updated_incident_pdf")
def generate_pdf_email_to_user_task(incident_id, user_email):
    try:
        # Fetch incident data based on incident_id
        try:
            incident = Incident.objects.get(pk=incident_id)
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
            "incident/incident_form_pdf.html", context
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

# this task sends incident forms to those on the external sedners list


@app.task(name='generate_and_send_pdf_task')
def generate_and_send_pdf_task(incident_id):
    try:
        # Fetch the incident
        incident = Incident.objects.get(pk=incident_id)

        # Generate the PDF
        pdf_data = create_pdf(incident_id)  # helper returns "data"

        if pdf_data.get("status") == "error":
            raise ValueError(pdf_data.get("message"))

        pdf_buffer = pdf_data.get("pdf_buffer")
        pdf_filename = pdf_data.get("pdf_filename")

        # Define email details
        # Fetch active external recipients
        to_emails = ExternalRecipient.objects.filter(
            is_active=True
            ).values_list("email", flat=True)
        subject = f"Incident Report: {incident.brief_description}"
        body = (
                f"<p>An incident occurred on {incident.eventdate} "
                f"at {incident.store}.</p>"
                f"<p>Details: {incident.brief_description}</p>"
                f"<p>Please find the incident report attached.</p>"
            )

        # Send the email
        send_incident_email(
            to_emails=to_emails,
            subject=subject,
            body=body,
            attachment_buffer=pdf_buffer,
            attachment_filename=pdf_filename,
        )

        # Mark the incident as sent
        incident.sent = True
        incident.sent_at = timezone.now()
        incident.save(update_fields=["sent", "sent_at"])

        return f"Incident {incident_id} processed and sent successfully."

    except Incident.DoesNotExist:
        logger.error(f"Incident with ID {incident_id} does not exist.")
        return f"Incident {incident_id} does not exist."

    except Exception as e:
        logger.error(f"Error processing incident {incident_id}: {str(e)}")
        return f"Error processing incident {incident_id}: {str(e)}"


