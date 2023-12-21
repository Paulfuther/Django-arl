import io

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.http import HttpResponse
from openpyxl import Workbook

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
    actions = ["print_user_details"]

    def print_user_details(self, request, queryset):
        # This action prints the details of selected active users to the terminal
        for user in queryset:
            if user.is_active:
                print(f"Username: {user.username}")
                print(f"Email: {user.email}")
                # Add more fields as needed
                print("")

    print_user_details.short_description = "Print User Details"

    actions = ["export_selected_users_to_excel"]

    def export_selected_users_to_excel(self, request, queryset):
        workbook = Workbook()
        sheet = workbook.active

        # Create the headers
        headers = [
            "Username",
            "Email",
            "First Name",
            "Last Name",
            "Phone Number",
            "address",
            "address_two",
            "city",
            "state_province",
            "postal",
            "country",
            "sin",
            "dob",
        ]
        sheet.append(headers)

        for user in queryset:
            country = user.country.name if user.country else None
            data = [
                user.username,
                user.email,
                user.first_name,
                user.last_name,
                user.phone_number,
                user.address,
                user.address_two,
                user.city,
                user.state_province,
                user.postal,
                country,
                user.sin,
                user.dob,
            ]
            sheet.append(data)

        virtual_workbook = io.BytesIO()
        workbook.save(virtual_workbook)
        virtual_workbook.seek(0)

        response = HttpResponse(
            virtual_workbook.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = "attachment; filename=selected_users.xlsx"

        return response

    export_selected_users_to_excel.short_description = "Export selected users to Excel"

    def get_groups(self, obj):
        return ", ".join([group.name for group in obj.groups.all()])

    get_groups.short_description = "Groups"


UserAdmin.fieldsets = tuple(fields)
admin.site.register(Employer)
admin.site.register(Twimlmessages)
admin.site.register(BulkEmailSendgrid)
admin.site.register(Store)
admin.site.register(Incident)
admin.site.register(EmailTemplate)
admin.site.register(DocuSignTemplate)
admin.site.register(CustomUser, CustomUserAdmin)
