from __future__ import absolute_import, unicode_literals

import logging
from io import BytesIO

import pdfkit
from django.core.exceptions import ObjectDoesNotExist
from django.template.loader import render_to_string
from django.utils.text import slugify

from arl.celery import app
from arl.dbox.helpers import upload_any_file_to_dropbox
from arl.helpers import get_s3_images_for_salt_log
from arl.quiz.models import SaltLog
from arl.user.models import CustomUser, Employer, Store

logger = logging.getLogger(__name__)


@app.task(name="save_salt_log")
def save_salt_log(**kwargs):
    try:
        # Extract form data
        store_id = kwargs.pop("store", None)
        user_employer_id = kwargs.pop("user_employer", None)
        user_id = kwargs.pop("user", None)
        # Get the Store instance using the store_id
        store_instance = (
            Store.objects.get(pk=store_id) if store_id is not None else None
        )
        user_employer_instance = (
            Employer.objects.get(pk=user_employer_id)
            if user_employer_id is not None
            else None
        )
        user_instance = (
            CustomUser.objects.get(pk=user_id)if user_id else None
        )
        # Set the Store instance back to the kwargs
        kwargs["store"] = store_instance
        kwargs["user_employer"] = user_employer_instance
        kwargs["user"] = user_instance
        # Save the form data to the database
        saltlog = SaltLog.objects.create(**kwargs)

        return {
            "incident_store": saltlog.id,
            "Incident_brief": saltlog.area_salted,
            "message": "Salt Log Created",
        }
    except CustomUser.DoesNotExist:
        error_message = f"User with ID {user_id} does not exist."
        logger.error(error_message)
        return {"error": error_message}
    except Store.DoesNotExist:
        error_message = f"Store with ID {store_id} does not exist."
        logger.error(error_message)
        return {"error": error_message}
    except Employer.DoesNotExist:
        error_message = f"Employer with ID {user_employer_id} does not exist."
        logger.error(error_message)
        return {"error": error_message}
    except Exception as e:
        logger.error(f"Error saving incident: {e}")
        return {"error": str(e)}


@app.task(name="create_salt_log_pdf")
def generate_salt_log_pdf_task(incident_id):
    try:
        # Fetch incident data based on incident_id
        try:
            incident = SaltLog.objects.get(pk=incident_id)
        except ObjectDoesNotExist:
            raise ValueError("Incident with ID {} does not exist.".
                             format(incident_id))

        images = get_s3_images_for_salt_log(
            incident.image_folder, incident.user_employer
        )
        context = {"incident": incident, "images": images}
        html_content = render_to_string("quiz/salt_log_form_pdf.html",
                                        context)
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
        date_salted_str = incident.date_salted.strftime("%Y-%m-%d") if incident.date_salted else "no-date"
        # Create a unique file name for the PDF using store number and brief
        # description
        pdf_filename = (
            f"{store_number}_{slugify(date_salted_str)}"
            f"_salte_log_report.pdf"
        )

        # Close the BytesIO buffer to free up resources
        # Set the BytesIO buffer's position to the beginning
        # Upload the PDF to Linode Object Storage
        object_key = (
            f"SALTLOGS/{incident.user_employer}/{incident.store}/"
            f"{pdf_filename}"
        )
        
        # Upload the PDF to Dropbox
        upload_any_file_to_dropbox(pdf, pdf_filename, object_key=object_key)
        # Set the BytesIO buffer's position to the beginning
        pdf_buffer.seek(0)

        # Close the BytesIO buffer to free up resources
        # Then email to the current user and all users in
        # the group incident_form_email
        return {
            "status": "success",
            "message": "PDF generated and uploaded successfully",
        }
    except Exception as e:
        logger.error("Error in generate_pdf_task: {}".format(e))
        return {"status": "error", "message": str(e)}
