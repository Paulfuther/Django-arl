
import logging
from io import BytesIO

import pdfkit
from django.core.exceptions import ObjectDoesNotExist
from django.template.loader import render_to_string
from django.utils.text import slugify

from arl.helpers import get_s3_images_for_incident

from .models import Incident

logger = logging.getLogger(__name__)


def create_pdf(incident_id):
    try:
        # Fetch incident data based on incident_id
        try:
            incident = Incident.objects.get(pk=incident_id)
        except ObjectDoesNotExist:
            raise ValueError("Incident with ID {} does not exist.".
                             format(incident_id))

        images = get_s3_images_for_incident(
            incident.image_folder, incident.user_employer
        )
        context = {"incident": incident, "images": images}
        html_content = render_to_string("incident/incident_form_pdf.html",
                                        context)
        #  Generate the PDF using pdfkit
        options = {
            "enable-local-file-access": None,
            "--keep-relative-links": "",
            "encoding": "UTF-8",
        }
        pdf_content = pdfkit.from_string(html_content, False, options)
        #  Create a BytesIO object to store the PDF content
        pdf_buffer = BytesIO(pdf_content)
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
        # Return the PDF as a BytesIO buffer
        return {
            "status": "success",
            "pdf_filename": pdf_filename,
            "pdf_buffer": pdf_buffer}

    except ObjectDoesNotExist:
        error_message = f"Incident with ID {incident_id} does not exist."
        logger.error(error_message)
        return {"status": "error", "message": error_message}

    except Exception as e:
        error_message = f"Error in create_pdf: {str(e)}"
        logger.error(error_message)
        return {"status": "error", "message": error_message}


def create_restricted_pdf(incident_id):
    try:
        # Fetch incident data based on incident_id
        try:
            incident = Incident.objects.get(pk=incident_id)
        except ObjectDoesNotExist:
            raise ValueError("Incident with ID {} does not exist.".
                             format(incident_id))

        context = {"incident": incident}
        html_content = render_to_string("incident/restricted_incident_form_pdf.html",
                                        context)
        #  Generate the PDF using pdfkit
        options = {
            "enable-local-file-access": None,
            "--keep-relative-links": "",
            "encoding": "UTF-8",
        }
        pdf_content = pdfkit.from_string(html_content, False, options)
        #  Create a BytesIO object to store the PDF content
        pdf_buffer = BytesIO(pdf_content)
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
        # Return the PDF as a BytesIO buffer
        return {"status": "success", "pdf_filename": pdf_filename, "pdf_buffer": pdf_buffer}

    except ObjectDoesNotExist:
        error_message = f"Incident with ID {incident_id} does not exist."
        logger.error(error_message)
        return {"status": "error", "message": error_message}

    except Exception as e:
        error_message = f"Error in create_pdf: {str(e)}"
        logger.error(error_message)
        return {"status": "error", "message": error_message}
