from django.apps import AppConfig


class MsgConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "arl.msg"


class DocusignAppConfig(AppConfig):  # Adjust based on your app name
    default_auto_field = "django.db.models.BigAutoField"
    name = "docusign_app"

    def ready(self):
        import dsign.signals  