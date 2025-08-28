from __future__ import absolute_import, unicode_literals

import logging
import time
import uuid
from datetime import datetime
from io import BytesIO

import pdfkit
import requests
from django.template.loader import render_to_string
from django.utils.text import slugify
from PIL import Image

from arl.celery import app
from arl.dbox.helpers import master_upload_file_to_dropbox
from arl.helpers import (
    get_s3_images_for_salt_log,
    get_signed_url_for_key,
    upload_to_linode_object_storage,
)
from arl.quiz.models import Checklist, SaltLog
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
        user_instance = CustomUser.objects.get(pk=user_id) if user_id else None
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
        date_salted_str = (
            incident.date_salted.strftime("%Y-%m-%d")
            if incident.date_salted
            else "no-date"
        )
        pdf_filename = f"{store_number}_{slugify(date_salted_str)}_salt_log_report.pdf"

        # Define folder structure parameters
        company_name = slugify(incident.user_employer.name)
        store_name = slugify(incident.store.number)
        current_year = datetime.now().strftime("%Y")
        current_month = datetime.now().strftime("%m-%B")
        folder_path = (
            f"/SALTLOGS/{company_name}/{current_year}/{current_month}/{store_name}"
        )

        # Define the full file path
        full_file_path = f"{folder_path}/{pdf_filename}"

        # Upload the file using the helper function
        upload_result = master_upload_file_to_dropbox(
            pdf_buffer.getvalue(), full_file_path
        )

        pdf_buffer.seek(0)  # Reset buffer position

        # Log or return the upload result
        if upload_result[0]:
            return {
                "status": "success",
                "message": "PDF generated and uploaded successfully",
            }
        else:
            raise Exception(upload_result[1])

    except SaltLog.DoesNotExist:
        error_msg = f"SaltLog with ID {incident_id} does not exist."
        logger.error(error_msg)
        return {"status": "error", "message": error_msg}
    except Exception as e:
        logger.error(f"Error in generate_salt_log_pdf_task: {e}")
        return {"status": "error", "message": str(e)}


@app.task(name="create_checklist_pdf", bind=True, max_retries=3)
def generate_checklist_pdf_task(self, checklist_id: int):
    checklist = (
        Checklist.objects.select_related("created_by", "submitted_by", "store")
        .prefetch_related("items")
        .get(pk=checklist_id)
    )
    t0 = time.time()
    logger.info("[PDF] start checklist_id=%s task_id=%s", checklist_id, self.request.id)

    try:
        checklist = (
            Checklist.objects.select_related("created_by", "submitted_by")
            .prefetch_related("items")
            .get(pk=checklist_id)
        )
        # --- store segment (folder + filename) ---
        store_label = None
        if getattr(checklist, "store", None):
            # prefer a store number if you have one; else name
            store_label = getattr(checklist.store, "number", None) or getattr(
                checklist.store, "name", None
            )
        store_segment = slugify(store_label or "no-store")
        logger.info(
            "[PDF] loaded checklist slug=%s title=%s", checklist.slug, checklist.title
        )

        # Build items + signed photo URLs
        items = []
        count_photos = 0
        for item in checklist.items.all().order_by("order", "id"):
            photo_url = None
            if item.photo and item.photo.name:
                photo_url = get_signed_url_for_key(item.photo.name, expires_in=3600)
                count_photos += 1
            items.append(
                {
                    "text": item.text,
                    "result": item.result,
                    "comment": item.comment,
                    "photo_url": photo_url,
                }
            )
        logger.info("[PDF] items=%d photos=%d", len(items), count_photos)

        store_number = None
        store_name = None
        if checklist.store:
            # change these attr names if your Store model differs
            store_number = getattr(checklist.store, "number", None)
            store_name = getattr(checklist.store, "name", None)
            # Render HTML
        html_content = render_to_string(
            "quiz/checklist_pdf.html",
            {
                "checklist": checklist,
                "items": items,
                "store_number": store_number,
                "store_name": store_name,
            },
        )
        logger.info("[PDF] html_len=%d", len(html_content))

        # Generate PDF
        pdf_options = {
            "enable-local-file-access": None,
            "encoding": "UTF-8",
            "--keep-relative-links": "",
        }
        pdf_bytes = pdfkit.from_string(html_content, False, options=pdf_options)
        logger.info("[PDF] pdf_size_bytes=%d", len(pdf_bytes))
        pdf_buffer = BytesIO(pdf_bytes)

        # Build Dropbox path
        company_name = slugify(
            getattr(
                getattr(checklist.created_by, "employer", None), "name", "no-company"
            )
        )
        today = datetime.now()
        year = today.strftime("%Y")
        month = today.strftime("%m-%B")
        slug = checklist.slug or slugify(checklist.title) or f"checklist-{checklist.id}"
        filename = f"{store_segment}_{slug}-{checklist.id}.pdf"
        folder_path = f"/CHECKLISTS/{company_name}/{year}/{month}/{store_segment}"
        full_file_path = f"{folder_path}/{filename}"
        logger.info("[PDF] upload_path=%s", full_file_path)

        # Upload
        ok, msg = master_upload_file_to_dropbox(pdf_buffer.getvalue(), full_file_path)
        pdf_buffer.close()

        if not ok:
            raise RuntimeError(msg or "Upload failed")

        # Persist (if you have these fields)
        update_fields = []
        if hasattr(checklist, "pdf_key"):
            checklist.pdf_key = full_file_path
            update_fields.append("pdf_key")
        if hasattr(checklist, "pdf_status"):
            checklist.pdf_status = "ready"
            update_fields.append("pdf_status")
        if hasattr(checklist, "pdf_generated_at"):
            checklist.pdf_generated_at = datetime.now()
            update_fields.append("pdf_generated_at")
        if update_fields:
            checklist.save(update_fields=update_fields)

        logger.info(
            "[PDF] done in %.2fs checklist_id=%s", time.time() - t0, checklist_id
        )
        return {"status": "success", "path": full_file_path}

    except Checklist.DoesNotExist:
        logger.error("[PDF] checklist not found id=%s", checklist_id)
        return {"status": "error", "message": f"Checklist {checklist_id} not found"}

    except Exception as e:
        logger.exception("[PDF] error checklist_id=%s err=%s", checklist_id, e)
        # Optional: mark error status on model
        try:
            checklist = Checklist.objects.get(pk=checklist_id)
            if hasattr(checklist, "pdf_status"):
                checklist.pdf_status = "error"
                checklist.save(update_fields=["pdf_status"])
        except Exception:
            pass
        return {"status": "error", "message": str(e)}


@app.task(name="generate_fresh_checklist_pdf")
def generate_fresh_checklist_pdf(checklist_id):
    try:
        checklist = (
            Checklist.objects
            .select_related("created_by", "submitted_by", "store")
            .prefetch_related("items")
            .get(pk=checklist_id)
        )
        logger.info("[PDF] Generating fresh PDF for checklist_id=%s title=%s",
                    checklist.id, checklist.title)

    except Checklist.DoesNotExist:
        logger.error("[PDF] Checklist id=%s does not exist", checklist_id)
        return None

    def _downscale_for_pdf(http_url: str, max_px=800, jpeg_quality=75):
        """
        Fetch image URL, downscale, upload to TEMP, return signed URL.
        """
        try:
            logger.debug("[PDF] Fetching image from %s", http_url)
            r = requests.get(http_url, timeout=20)
            r.raise_for_status()
            im = Image.open(BytesIO(r.content)).convert("RGB")
            im.thumbnail((max_px, max_px), Image.LANCZOS)

            buf = BytesIO()
            im.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
            buf.seek(0)

            tmp_key = f"TEMP/pdf-thumbs/{uuid.uuid4().hex}.jpg"
            upload_to_linode_object_storage(buf, tmp_key)
            buf.close()

            signed_url = get_signed_url_for_key(tmp_key, expires_in=900)
            logger.debug("[PDF] Uploaded downscaled image to %s", tmp_key)
            return signed_url
        except Exception as e:
            logger.warning("[PDF] Could not process image %s: %s", http_url, e)
            return None

    # Build items
    items = []
    for it in checklist.items.all().order_by("order", "id"):
        photo_url = None
        if it.photo and it.photo.name:
            orig = get_signed_url_for_key(it.photo.name, expires_in=900)
            photo_url = _downscale_for_pdf(orig, max_px=800, jpeg_quality=75)
        items.append({
            "text": it.text,
            "result": it.result,
            "comment": it.comment,
            "photo_url": photo_url,
        })
    logger.info("[PDF] Collected %s items for checklist_id=%s", len(items), checklist.id)

    # Render template
    html = render_to_string(
        "quiz/checklist_pdf.html",
        {
            "checklist": checklist,
            "items": items,
            "store_number": getattr(checklist.store, "number", None),
            "store_name": getattr(checklist.store, "name", None),
        },
    )
    logger.debug("[PDF] Rendered HTML for checklist_id=%s", checklist.id)

    # Generate PDF
    try:
        options = {
            "enable-local-file-access": None,
            "encoding": "UTF-8",
            "--keep-relative-links": "",
        }
        pdf_bytes = pdfkit.from_string(html, False, options=options)
        logger.info("[PDF] PDF generated successfully for checklist_id=%s", checklist.id)
    except Exception as e:
        logger.exception("[PDF] Failed to generate PDF for checklist_id=%s: %s", checklist.id, e)
        return None

    pdf_buffer = BytesIO(pdf_bytes)

    # Upload to TEMP folder
    tmp_id = uuid.uuid4().hex
    filename = f"fresh-{slugify(checklist.slug or checklist.title)}-{tmp_id}.pdf"
    folder_path = f"TEMP/{datetime.now().strftime('%Y/%m/%d')}"
    full_path = f"{folder_path}/{filename}"

    try:
        upload_to_linode_object_storage(pdf_buffer, full_path)
        logger.info("[PDF] Uploaded fresh PDF to %s for checklist_id=%s", full_path, checklist.id)
    except Exception as e:
        logger.exception("[PDF] Upload failed for checklist_id=%s: %s", checklist.id, e)
        return None
    finally:
        pdf_buffer.close()

    return full_path