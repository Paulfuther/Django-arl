from django.apps import AppConfig


class UserConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "arl.user"

    def ready(self):
        import arl.user.signals  # Ensure signals are loaded
