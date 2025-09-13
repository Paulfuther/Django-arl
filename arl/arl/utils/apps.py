from django.apps import AppConfig
from pillow_heif import register_heif_opener
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class UtilsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "arl.utils"

    def ready(self):
        # ✅ Register HEIC/HEIF opener once at startup
        register_heif_opener()

        # ✅ Increase Pillow’s pixel limit (default is ~89M, but safer to cap lower)
        Image.MAX_IMAGE_PIXELS = 50_000_000  # 50 million pixels (adjust if needed)
        logger.info("✅ UtilsConfig.ready(): HEIC registered, pixel limit set to %s", Image.MAX_IMAGE_PIXELS)
        print(">>> UtilsConfig.ready() ran")  # fallback if logging not visible
