# tasks.py
import os
import logging
from arl.celery import app
from arl.utils.images import normalize_to_jpeg

from arl.bucket.helpers import upload_to_linode_object_storage
from arl.dsign.models import SignedDocumentFile

from .models import StoreDocumentJob

logger = logging.getLogger(__name__)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".gif", ".heic", ".heif"}


def _is_image(name: str, ct: str) -> bool:
    ext = (os.path.splitext(name)[1] or "").lower()
    return ext in IMAGE_EXTS or (ct or "").startswith("image/")


@app.task(
    name="process_store_docuemnts_task",
    bind=True,
    max_retries=3,
    default_retry_delay=15,
)
def process_store_document_task(self, job_id: str):
    job = StoreDocumentJob.objects.get(pk=job_id)
    job.status = "processing"
    job.save(update_fields=["status"])

    try:
        sdf = SignedDocumentFile.objects.get(pk=job.sdf_id)
        dest_key = sdf.file_path

        # A) Images → normalize to ~0.9 MB JPEG (store docs need readability)
        if _is_image(job.original_name, job.original_ct):
            logger.info(
                "[StoreDocTask] Normalizing image name=%s ct=%s",
                job.original_name,
                job.original_ct,
            )
            with open(job.tmp_path, "rb") as f:
                buf, _ = normalize_to_jpeg(
                    f,
                    target_long_edge=2000,
                    target_bytes=900_000,
                    min_q=60,
                    max_q=92,
                )
            if hasattr(buf, "seek"):
                buf.seek(0)
            upload_to_linode_object_storage(buf, dest_key)
            if hasattr(buf, "close"):
                buf.close()
            logger.info("[StoreDocTask] Uploaded normalized image to %s", dest_key)

        # B) Non-images → stream original
        else:
            logger.info(
                "[StoreDocTask] Uploading raw file name=%s ct=%s",
                job.original_name,
                job.original_ct,
            )
            with open(job.tmp_path, "rb") as fp:
                if hasattr(fp, "seek"):
                    fp.seek(0)
                upload_to_linode_object_storage(fp, dest_key)
            logger.info("[StoreDocTask] Uploaded raw file to %s", dest_key)

        # done: nothing to change on SDF (it already has the final key)
        job.status = "done"
        job.save(update_fields=["status"])
        logger.info("[StoreDocTask] Job %s marked as done", job_id)

    except Exception as e:
        logger.exception("[StoreDocTask] Job %s failed: %s", job_id, e)
        # Roll back the SDF so you don’t have a dangling record
        try:
            SignedDocumentFile.objects.filter(pk=job.sdf_id).delete()
            logger.warning(
                "[StoreDocTask] Deleted SDF id=%s due to failure", job.sdf_id
            )
        except Exception:
            pass
        job.status = "error"
        job.error = str(e)
        job.save(update_fields=["status", "error"])
        raise
    finally:
        try:
            os.remove(job.tmp_path)
            logger.info("[StoreDocTask] Temp file removed: %s", job.tmp_path)
        except Exception as rm_err:
            logger.warning(
                "[StoreDocTask] Could not remove temp file %s: %s", job.tmp_path, rm_err
            )
