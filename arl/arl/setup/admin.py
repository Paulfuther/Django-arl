from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html

# from arl.payroll.models import CalendarEvent, PayPeriod, StatutoryHoliday
from arl.setup.models import EmployerRequest

# Register your models here.


class EmployerRequestAdmin(admin.ModelAdmin):
    list_display = [
        "company_name",
        "email",
        "phone_number",
        "status",
        "stripe_plan",
        "approve_button",
    ]
    actions = ["approve_selected_requests"]

    def approve_button(self, obj):
        url = reverse("approve_employer", args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" style="padding:2px 8px;">Approve</a>', url
        )

    approve_button.short_description = "Approve Employer"

    def approve_selected_requests(self, request, queryset):
        approved_count = 0

        for obj in queryset:
            if obj.status == "pending":
                # Call your approval logic here (if needed)
                obj.status = "approved"
                obj.save()
                approved_count += 1

        if approved_count > 0:
            messages.success(
                request, f"Successfully approved {approved_count} employer(s)."
            )
        else:
            messages.warning(request, "No pending employer requests were selected.")

        return redirect("/admin/setup/employerrequest/")

    approve_selected_requests.short_description = "Approve selected employer requests"


admin.site.register(EmployerRequest, EmployerRequestAdmin)
