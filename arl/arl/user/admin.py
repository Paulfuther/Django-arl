from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from arl.dsign.models import DocuSignTemplate
from arl.incident.models import Incident
from arl.msg.models import BulkEmailSendgrid, EmailTemplate, Twimlmessages

from .models import CustomUser, Employer, Store

fields = list(UserAdmin.fieldsets)

fields[1] = (
    "Personal Info",
    {
        "fields": (
            "employer",
            "first_name",
            "last_name",
            "address",
            "address_two",
            "city",
            "state_province",
            "postal",
            "country",
            "dob",
            "sin",
            "email",
            "phone_number",
        )
    },
)


class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "is_active",
        "get_groups",
    )  # Customize the fields you want to display
    list_filter = ("is_active", "groups")  # Add any filters you need

    def get_groups(self, obj):
        return ", ".join([group.name for group in obj.groups.all()])

    get_groups.short_description = "Groups"

    fieldsets = list(UserAdmin.fieldsets)
    fieldsets[1] = (
        "Personal Info",
        {
            "fields": (
                "employer",
                "first_name",
                "last_name",
                "address",
                "address_two",
                "city",
                "state_province",
                "postal",
                "country",
                "dob",
                "sin",
                "phone_number",
            )
        },
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "employer",
                    "username",
                    "email",
                    "password1",
                    "password2",
                    "first_name",
                    "last_name",
                    "address",
                    "address_two",
                    "city",
                    "state_province",
                    "postal",
                    "country",
                    "dob",
                    "sin",
                    "phone_number",
                ),
            },
        ),
    )


UserAdmin.fieldsets = tuple(fields)
admin.site.register(Employer)
admin.site.register(Twimlmessages)
admin.site.register(BulkEmailSendgrid)
admin.site.register(Store)
admin.site.register(Incident)
admin.site.register(EmailTemplate)
admin.site.register(DocuSignTemplate)
admin.site.register(CustomUser, CustomUserAdmin)
