import io

import openpyxl
from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.auth import login
from django.contrib.auth.admin import UserAdmin
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views import View
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from twilio.base.exceptions import TwilioException
from .views import CustomAdminLoginView
from arl.incident.models import Incident
from arl.msg.helpers import request_verification_token
from arl.msg.models import BulkEmailSendgrid, Twimlmessages

from .models import CustomUser, Employer, Store

fields = list(UserAdmin.fieldsets)
fields[1] = (
    "Personal Info",
    {
        "fields": (
            "employer",
            "first_name",
            "last_name",
            "sin",
            "email",
            "phone_number",
            "mon_avail",
            "tue_avail",
            "wed_avail",
            "thu_avail",
            "fri_avail",
            "sat_avail",
            "sun_avail",
        )
    },
)


class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "is_active",
    )  # Customize the fields you want to display
    list_filter = ("is_active",)  # Add any filters you need
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
        headers = ["Username", "Email", "First Name", "Last Name", "Phone Number"]
        sheet.append(headers)

        for user in queryset:
            data = [user.username, user.email, user.first_name, user.last_name, user.phone_number]
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

UserAdmin.fieldsets = tuple(fields)
admin.site.register(Employer)
admin.site.register(Twimlmessages)
admin.site.register(BulkEmailSendgrid)
admin.site.register(Store)
admin.site.register(Incident)
admin.site.register(CustomUser, CustomUserAdmin)
