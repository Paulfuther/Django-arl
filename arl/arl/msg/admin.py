from django.contrib import admin
from .models import ComplianceFile


@admin.register(ComplianceFile)
class ComplianceFileAdmin(admin.ModelAdmin):
    list_display = ("title", "uploaded_at", "is_active")
    list_filter = ("is_active",)
    search_fields = ("title",)

    def save_model(self, request, obj, form, change):
        if obj.is_active:
            ComplianceFile.objects.exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)
