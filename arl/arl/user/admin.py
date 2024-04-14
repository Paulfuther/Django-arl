from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from import_export import resources
from import_export.admin import ExportActionMixin

from arl.dsign.models import DocuSignTemplate, ProcessedDocsignDocument
from arl.incident.models import Incident
from arl.msg.models import (
    BulkEmailSendgrid,
    EmailTemplate,
    Twimlmessages,
    WhatsAppTemplate,
)

from .models import CustomUser, Employer, Store, UserManager

fields = list(UserAdmin.fieldsets)


class UserResource(resources.ModelResource):
    class Meta:
        model = CustomUser
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "phone_number",
        )


class CustomUserAdmin(ExportActionMixin, UserAdmin):
    resource_class = UserResource
    list_display = (
        "username",
        "email",
        "phone_number",
        "last_login",
        "is_active",
        "get_groups",
    )  # Customize the fields you want to display
    list_filter = ("is_active", "groups")  # Add any filters you need

    # def has_delete_permission(self, request, obj=None):
    #    return False  # Disables the ability to delete users

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
                "email",
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

    def save_model(self, request, obj, form, change):
        # Ensure 'phone_number' is saved when creating/updating a user
        obj.phone_number = form.cleaned_data.get("phone_number", "")
        super().save_model(request, obj, form, change)


class IncidentAdmin(admin.ModelAdmin):
    list_display = ("store", "brief_description", "eventdate")
    search_fields = ("store__number", "brief_description")
    list_filter = ("eventdate",)


UserAdmin.fieldsets = tuple(fields)
admin.site.register(Employer)
admin.site.register(Twimlmessages)
admin.site.register(BulkEmailSendgrid)
admin.site.register(Store)
admin.site.register(Incident, IncidentAdmin)
admin.site.register(EmailTemplate)
admin.site.register(DocuSignTemplate)
admin.site.register(ProcessedDocsignDocument)
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(UserManager)
admin.site.register(WhatsAppTemplate)
