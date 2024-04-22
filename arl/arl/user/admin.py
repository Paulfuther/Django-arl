from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from import_export import fields as export_fields
from import_export import resources
from import_export.admin import ExportActionMixin

from arl.dsign.models import DocuSignTemplate, ProcessedDocsignDocument
from arl.incident.models import Incident
from arl.msg.models import (
    BulkEmailSendgrid,
    EmailTemplate,
    Twimlmessages,
    UserConsent,
    WhatsAppTemplate,
)

from .models import CustomUser, Employer, Store, UserManager

# fields = list(UserAdmin.fieldsets)


class UserResource(resources.ModelResource):
    manager = export_fields.Field()
    whatsapp_consent = export_fields.Field()

    class Meta:
        model = CustomUser
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "manager",
            "whatsapp_consent",
        )
        export_order = (
            "username",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "manager",
            "whatsapp_consent",
        )

    def dehydrate_manager(self, custom_user):
        # Assuming a reverse ForeignKey from UserManager to CustomUser as 'managed_users'
        user_manager = UserManager.objects.filter(user=custom_user).first()
        return (
            user_manager.manager.username
            if user_manager and user_manager.manager
            else "None"
        )

    def dehydrate_whatsapp_consent(self, custom_user):
        consent = UserConsent.objects.filter(
            user=custom_user, consent_type="WhatsApp"
        ).first()
        return "Granted" if consent and consent.is_granted else "Not Granted"


class CustomUserAdmin(ExportActionMixin, UserAdmin):
    resource_class = UserResource
    # Customize the fields you want to display
    list_display = (
        "username",
        "email",
        "phone_number",
        "last_login",
        "is_active",
        "get_groups",
        "get_manager",
        "get_consent",
    )
    list_filter = ("is_active", "groups")  # Add any filters you need

    # def has_delete_permission(self, request, obj=None):
    #    return False  # Disables the ability to delete users

    def get_groups(self, obj):
        return ", ".join([group.name for group in obj.groups.all()])

    get_groups.short_description = "Groups"

    def get_manager(self, obj):
        user_manager = UserManager.objects.filter(user=obj).first()
        return (
            user_manager.manager.username
            if user_manager and user_manager.manager
            else "None"
        )

    get_manager.short_description = "Manager"

    def get_consent(self, obj):
        consent = UserConsent.objects.filter(user=obj, consent_type="WhatsApp").first()
        return "Granted" if consent and consent.is_granted else "Not Granted"

    get_consent.short_description = "WhatsApp Consent"

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


@admin.register(UserManager)
class UserManagerAdmin(admin.ModelAdmin):
    list_display = ("user", "get_manager")

    def get_manager(self, obj):
        return obj.manager.username if obj.manager else "No Manager"

    get_manager.short_description = "Manager"

    search_fields = ["user__username", "manager__username"]


@admin.register(UserConsent)
class UserConsentAdmin(admin.ModelAdmin):
    list_display = ("user", "consent_type", "is_granted", "granted_on", "revoked_on")
    list_filter = ("consent_type", "is_granted")
    search_fields = ("user__username",)


# UserAdmin.fieldsets = tuple(fields)
admin.site.register(Employer)
admin.site.register(Twimlmessages)
admin.site.register(BulkEmailSendgrid)
admin.site.register(Store)
admin.site.register(Incident, IncidentAdmin)
admin.site.register(EmailTemplate)
admin.site.register(DocuSignTemplate)
admin.site.register(ProcessedDocsignDocument)
admin.site.register(CustomUser, CustomUserAdmin)
# admin.site.register(UserManager)
admin.site.register(WhatsAppTemplate)
