from django.contrib import admin
from .models import RecruitApplicant


@admin.register(RecruitApplicant)
class RecruitApplicantAdmin(admin.ModelAdmin):
    list_display = (
        "first_name",
        "last_name",
        "email",
        "phone_number",
        "source",
        "status",
        "created_at",
    )
    list_filter = ("source", "status", "created_at")
    search_fields = ("first_name", "last_name", "email", "phone_number")
