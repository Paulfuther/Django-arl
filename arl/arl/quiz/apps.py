from django.apps import AppConfig
from pillow_heif import register_heif_opener
from PIL import Image


class QuizConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "arl.quiz"

    def ready(self):
        # ✅ Register HEIC/HEIF opener once at startup
        register_heif_opener()

        # ✅ Increase Pillow’s pixel limit (default is ~89M, but safer to cap lower)
        Image.MAX_IMAGE_PIXELS = 50_000_000  # 50 million pixels (adjust if needed)
