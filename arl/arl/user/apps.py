from django.apps import AppConfig
from django.contrib import admin


class UserConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "arl.user"

    def ready(self):
        # Ensure signals are still loaded

        # ✅ Safe override of django_celery_results admin
        from django_celery_results.models import TaskResult
        from arl.user.admin import CustomTaskResultAdmin

        try:
            admin.site.unregister(TaskResult)
        except admin.sites.NotRegistered:
            pass

        admin.site.register(TaskResult, CustomTaskResultAdmin)
        print("✅ Custom TaskResultAdmin loaded and registered from AppConfig")
