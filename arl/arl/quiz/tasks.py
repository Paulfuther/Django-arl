from __future__ import absolute_import, unicode_literals

import logging
from datetime import datetime
from io import BytesIO

import pdfkit
from django.template.loader import render_to_string
from django.utils.text import slugify

from arl.celery import app
from arl.dbox.helpers import master_upload_file_to_dropbox
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
        # Fetch the salt log data
        incident = SaltLog.objects.get(pk=incident_id)

        # Get associated images
        images = get_s3_images_for_salt_log(
            incident.image_folder, incident.user_employer
        )

        # Prepare the context for rendering the PDF
        context = {"incident": incident, "images": images}
        html_content = render_to_string("quiz/salt_log_form_pdf.html", context)

        # Generate the PDF using pdfkit
        pdf_options = {
            "enable-local-file-access": None,
            "--keep-relative-links": "",
            "encoding": "UTF-8",
        }
        pdf = pdfkit.from_string(html_content, False, pdf_options)
        pdf_buffer = BytesIO(pdf)  # Create a BytesIO object to store the PDF content

        # Generate a unique filename
        store_number = incident.store.number
        date_salted_str = incident.date_salted.strftime("%Y-%m-%d") if incident.date_salted else "no-date"
        pdf_filename = f"{store_number}_{slugify(date_salted_str)}_salt_log_report.pdf"

        # Define folder structure parameters
        company_name = slugify(incident.user_employer.name)
        store_name = slugify(incident.store.number)
        current_year = datetime.now().strftime("%Y")
        current_month = datetime.now().strftime("%m-%B")
        folder_path = f"/SALTLOGS/{company_name}/{current_year}/{current_month}/{store_name}"

        # Define the full file path
        full_file_path = f"{folder_path}/{pdf_filename}"

        # Upload the file using the helper function
        upload_result = master_upload_file_to_dropbox(
            pdf_buffer.getvalue(), full_file_path
        )
        
        pdf_buffer.seek(0)  # Reset buffer position

        # Log or return the upload result
        if upload_result[0]:
            return {"status": "success", "message": "PDF generated and uploaded successfully"}
        else:
            raise Exception(upload_result[1])

    except SaltLog.DoesNotExist:
        error_msg = f"SaltLog with ID {incident_id} does not exist."
        logger.error(error_msg)
        return {"status": "error", "message": error_msg}
    except Exception as e:
        logger.error(f"Error in generate_salt_log_pdf_task: {e}")
        return {"status": "error", "message": str(e)}