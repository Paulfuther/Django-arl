from django.apps import AppConfig
from pillow_heif import register_heif_opener
register_heif_opener()


class QuizConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "arl.quiz"
