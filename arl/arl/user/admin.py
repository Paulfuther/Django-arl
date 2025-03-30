from datetime import datetime
from django.forms.widgets import TextInput
from django import forms
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from import_export import fields
from import_export import fields as export_fields
from import_export import resources
from import_export.admin import ExportActionMixin
import uuid
from django.utils.html import strip_tags
from arl.carwash.models import CarwashStatus
from arl.dsign.models import (DocuSignTemplate, ProcessedDocsignDocument,
                              SignedDocumentFile)
from arl.incident.models import Incident, MajorIncident
from arl.msg.models import (BulkEmailSendgrid, EmailTemplate, Twimlmessages,
                            UserConsent, WhatsAppTemplate)
from arl.msg.tasks import EmployerSMSTask
# from arl.payroll.models import CalendarEvent, PayPeriod, StatutoryHoliday
from arl.quiz.models import Answer, Question, Quiz, SaltLog

from .models import (CustomUser, DocumentType, EmployeeDocument, Employer,
                     ExternalRecipient, SMSOptOut, Store, UserManager,
                     EmployerSettings, NewHireInvite, EmployerRequest)
from arl.setup.models import TenantApiKeys
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import path
from arl.bucket.helpers import upload_to_linode_object_storage
from django.shortcuts import render, redirect


class ExternalRecipientAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'company', 'email', 'group')
    search_fields = ('first_name', 'last_name', 'company', 'email',
                     'group__name')


# This calss is used for exporting
class UserResource(resources.ModelResource):
    manager = export_fields.Field()
    whatsapp_consent = export_fields.Field()
    store = fields.Field(column_name="store", readonly=True)
    all_docusign_templates = fields.Field(column_name="Docusign Documents",
                                          attribute="all_docusign_templates")
    work_permit_expiration_date = fields.Field(column_name="Permit Expiration",
                                               attribute=(
                                                "work_permit_expiration_date"))
    sin_expiration_date = fields.Field(column_name="SIN Expiration",
                                       attribute="sin_expiration_date")

    class Meta:
        model = CustomUser
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "store",
            "phone_number",
            "manager",
            "whatsapp_consent",
            "sin",
            "sin_expiration_date",
            "work_permit_expiration_date",
            "all_docusign_templates",
        )
        export_order = fields
        queryset = CustomUser.objects.select_related("store").prefetch_related(
            "managed_users")
        queryset = CustomUser.objects.prefetch_related(
            "processeddocsigndocument_set")

    def dehydrate_manager(self, custom_user):
        # Fetch the first related UserManager object
        user_manager = UserManager.objects.filter(user=custom_user).first()

        # Check if the user_manager exists and has a manager
        if user_manager and user_manager.manager:
            return user_manager.manager.username
        return "None"

    def dehydrate_whatsapp_consent(self, custom_user):
        consent = UserConsent.objects.filter(
            user=custom_user, consent_type="WhatsApp"
        ).first()
        return "Granted" if consent and consent.is_granted else "Not Granted"

    def dehydrate_store(self, obj):
        return obj.store.number if obj.store else "No Store Assigned"

    def dehydrate_all_docusign_templates(self, obj):
        """Retrieve and format all DocuSign template names for a user."""
        templates = ProcessedDocsignDocument.objects.filter(user=obj).values_list("template_name", flat=True)
        if not templates:
            return "No Documents"
        return ", ".join(strip_tags(template) for template in templates) 


class SINFirstDigitFilter(SimpleListFilter):
    title = "SIN First Digit"  # Display title for the filter
    parameter_name = "sin_first_digit"  # Query parameter name in the URL

    def lookups(self, request, model_admin):
        # Define filter options
        return [
            ("9", "Starts with 9"),
            ("other", "Other"),
        ]

    def queryset(self, request, queryset):
        # Apply filtering logic
        value = self.value()
        if value == "9":
            return queryset.filter(sin__startswith="9")
        elif value == "other":
            return queryset.exclude(sin__startswith="9")
        return queryset


# Inline model to display all associated DocuSign documents
class ProcessedDocusignDocumentInline(admin.TabularInline):  # Or use admin.StackedInline for a different layout
    model = ProcessedDocsignDocument
    extra = 0  # Don't show empty extra forms
    fields = ("template_name", "processed_at")  # Adjust based on available fields
    readonly_fields = ("template_name", "processed_at")  # Make these fields non-editable


# CustomUser model
class CustomUserAdmin(ExportActionMixin, UserAdmin):
    resource_class = UserResource

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name in ["sin_expiration_date", "work_permit_expiration_date"]:
            kwargs["widget"] = TextInput(attrs={"type": "date"})  # ✅ Uses native date input, no calendar
        return super().formfield_for_dbfield(db_field, request, **kwargs)
    
    # Customize the fields you want to display
    inlines = [ProcessedDocusignDocumentInline]
    list_display = (
        "is_active",
        "username",
        "email",
        "store_number",
        'employer',
        "phone_number",
        "sin",
        "get_consent",
        "sin_expiration_date",
        "work_permit_expiration_date",
        "all_docusign_templates",
        "last_login",
        "get_groups",
    )
    list_filter = ("is_active", "groups", 'sin_expiration_date',
                   'work_permit_expiration_date', SINFirstDigitFilter)
    search_fields = ("username", "email", "phone_number", "sin")
    list_editable = ('sin_expiration_date', 'work_permit_expiration_date','phone_number')
    list_per_page = 15
    # def has_delete_permission(self, request, obj=None):
    #    return False  # Disables the ability to delete users

    def store_number(self, obj):
        """Retrieve only the store number for display in the admin."""
        return obj.store.number if obj.store else "None"

    store_number.short_description = "Store"

    def get_groups(self, obj):
        return ", ".join([group.name for group in obj.groups.all()])

    get_groups.short_description = "Groups"

    def expandable_groups(self, obj):
        """Creates an expandable section for groups."""
        groups = ", ".join([group.name for group in obj.groups.all()]
                           ) or "No Groups"
        return format_html(
            '<button class="expand-btn" onclick="toggleGroups(this)">Show Groups</button>'
            '<div class="group-list" style="display: none; padding: 5px; border: 1px solid #ddd; background: #f9f9f9;">{}</div>',
            groups
        )

    expandable_groups.short_description = "Groups"

    def all_docusign_templates(self, obj):
        """Display all template names for a user in a neat format."""
        templates = ProcessedDocsignDocument.objects.filter(
            user=obj
                ).values_list(
                    "template_name", flat=True)

        if not templates:
            return "No Documents"

        # Convert None values to empty strings
        formatted_templates = "<br>".join(filter(None, templates))

        return format_html(formatted_templates)

    all_docusign_templates.short_description = "Docusign Documents"

    def get_consent(self, obj):
        consent = UserConsent.objects.filter(user=obj,
                                             consent_type="WhatsApp").first()
        return "Granted" if consent and consent.is_granted else "Not Granted"

    get_consent.short_description = "WhatsApp Consent"

    fieldsets = list(UserAdmin.fieldsets)
    fieldsets[1] = (
        "Personal Info",
        {
            "fields": (
                "employer",
                "store",
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
                    "store",
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
        """Ensure phone_number is not overwritten when updating other fields."""
        if "phone_number" in form.cleaned_data and form.cleaned_data["phone_number"]:  
            obj.phone_number = form.cleaned_data["phone_number"]  # ✅ Update if provided
        else:
            obj.phone_number = CustomUser.objects.get(pk=obj.pk).phone_number  # ✅ Keep existing phone number

        super().save_model(request, obj, form, change)


class IncidentAdmin(admin.ModelAdmin):
    list_display = ("store", "brief_description", "eventdate")
    search_fields = ("store__number", "brief_description")
    list_filter = ("eventdate",)


class MajorIncidentAdmin(admin.ModelAdmin):
    list_display = ("store", "brief_description", "eventdate")
    search_fields = ("store__number", "brief_description")
    list_filter = ("eventdate",)


@admin.register(UserManager)
class UserManagerAdmin(admin.ModelAdmin):
    list_display = ("user", "get_manager", "user_creation_date")

    def get_manager(self, obj):
        return obj.manager.username if obj.manager else "No Manager"

    get_manager.short_description = "Manager"

    def user_creation_date(self, obj):

        return obj.user.date_joined.strftime("%Y-%m-%d")

    user_creation_date.short_description = "User Creation Date"

    search_fields = ["user__username", "manager__username"]


@admin.register(UserConsent)
class UserConsentAdmin(admin.ModelAdmin):
    list_display = ("user", "consent_type", "is_granted", "granted_on",
                    "revoked_on")
    list_filter = ("consent_type", "is_granted")
    search_fields = ("user__username",)


class StoreAdmin(admin.ModelAdmin):
    list_display = ("number", "employer", "manager")
    search_fields = ("number", "employer__name", "manager__username")


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 1  # Allow adding one extra answer by default
    fields = ['text', 'is_correct']


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1  # Allow adding one extra question by default
    # Do not attempt to nest inlines here; just show questions.


class QuizAdmin(admin.ModelAdmin):
    inlines = [QuestionInline]
    # Display questions inline within the Quiz admin view
    list_display = ('title', 'description')
    # Display quiz title and description in the list view

    def get_queryset(self, request):
        # Preload related questions and answers to avoid multiple database hits
        return (super().get_queryset(request).
                prefetch_related('questions__answers'))

    def view_questions_and_answers(self, obj):
        # Display questions and their answers as a
        # read-only field in the list view
        questions = obj.questions.all()
        html = ""
        for question in questions:
            html += f"<strong>{question.text}</strong><br>"
            answers = question.answers.all()
            for answer in answers:
                html += f"&nbsp;&nbsp;- {answer.text} "
                f"{'(Correct)' if answer.is_correct else ''}<br>"
        return format_html(html)

    view_questions_and_answers.short_description = 'Questions and Answers'


class QuestionAdmin(admin.ModelAdmin):
    inlines = [AnswerInline]  # Include AnswerInline in the QuestionAdmin
    list_display = ('text', 'quiz', 'display_answers')
    # Display the question text, quiz, and answers

    def display_answers(self, obj):
        answers = obj.answers.all()
        return [f"{answer.text} " for answer in answers]

    display_answers.short_description = 'Answers'


class TaskResultAdmin(admin.ModelAdmin):
    list_display = ('task_id', 'task_name', 'status', 'date_done', 'worker', 'short_result', 'created_datetime', 'completed_datetime')
    readonly_fields = (
        'task_id', 'task_name', 'status', 'worker', 
        'result_content_type', 'result_encoding', 'result', 
        'parameters', 'traceback', 'meta', 
        'created_datetime', 'completed_datetime'
    )
    list_filter = ('status', 'date_done')
    search_fields = ('task_id', 'task_name')

    def short_result(self, obj):
        """Shorten the result for list view."""
        if obj.result:
            return str(obj.result)[:75] + "..." if len(str(obj.result)) > 75 else obj.result
        return "No result"
    short_result.short_description = 'Result (short)'

    def created_datetime(self, obj):
        """Convert created datetime to local timezone for better readability."""
        return self._format_datetime(obj.date_created)
    created_datetime.short_description = "Created DateTime"

    def completed_datetime(self, obj):
        """Convert completed datetime to local timezone for better readability."""
        return self._format_datetime(obj.date_done)
    completed_datetime.short_description = "Completed DateTime"

    def _format_datetime(self, value):
        if value:
            # Customize this to match your timezone setup
            return datetime.strftime(value, "%b. %d, %Y, %I:%M %p")
        return "N/A"

    def parameters(self, obj):
        """Display formatted parameters for better readability."""
        args = obj.task_args or "-"
        kwargs = obj.task_kwargs or "-"
        return format_html(
            "<strong>Positional Arguments:</strong> {}<br><strong>Named Arguments:</strong> {}",
            args,
            kwargs,
        )
    parameters.short_description = 'Task Parameters'


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


@admin.register(EmployeeDocument)
class EmployeeDocumentAdmin(admin.ModelAdmin):
    list_display = ("user", "document_type", "issue_date", "expiration_date", "is_expired")
    list_filter = ("document_type", "expiration_date")
    search_fields = ("user__username", "user__email", "document_type__name", "document_number")
    date_hierarchy = "expiration_date"


@admin.register(SaltLog)
class SaltLogAdmin(admin.ModelAdmin):
    list_display = (
        'store',
        'user',
        'area_salted',
        'date_salted',
        'time_salted',
        'hidden_timestamp',
    )
    list_filter = ('store', 'date_salted')
    search_fields = ('store__name', 'area_salted')


@admin.register(CarwashStatus)
class CarwashStatusAdmin(admin.ModelAdmin):
    list_display = ("store", "status", "reason", "date_time", "updated_by")
    list_filter = ("status", "date_time", "store")
    search_fields = ("store__number", "status", "reason")
    ordering = ("-date_time",)

    def has_delete_permission(self, request, obj=None):
        """Allow deletion of records."""
        return True  # Ensure deletion is allowed

    def has_change_permission(self, request, obj=None):
        """Ensure records can be modified."""
        return True  # Modify this if you need restrictions

    def has_add_permission(self, request):
        """Allow adding new records."""
        return True


class SMSOptOutResource(resources.ModelResource):
    """Defines the data to export"""
    first_name = resources.Field()
    last_name = resources.Field()
    phone_number = resources.Field()

    class Meta:
        model = SMSOptOut
        fields = ("user__first_name", "user__last_name", "user__phone_number", "date_added")
        export_order = ("user__first_name", "user__last_name", "user__phone_number", "date_added")

    def dehydrate_first_name(self, obj):
        return obj.user.first_name if obj.user else ""

    def dehydrate_last_name(self, obj):
        return obj.user.last_name if obj.user else ""

    def dehydrate_phone_number(self, obj):
        return obj.user.phone_number if obj.user else ""


class SMSOptOutForm(forms.ModelForm):
    class Meta:
        model = SMSOptOut
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Sort users by phone number (or change to 'first_name'/'last_name')
        self.fields["user"].queryset = CustomUser.objects.filter(is_active=True).order_by("phone_number")
        self.fields["user"].label_from_instance = self.format_user_label

    def format_user_label(self, user):
        """Format how users appear in the dropdown."""
        return f"{user.first_name} {user.last_name} ({user.phone_number})"


class SMSOptOutAdmin(ExportActionMixin, admin.ModelAdmin):
    form = SMSOptOutForm
    resource_class = SMSOptOutResource
    list_display = ("get_first_name", "get_last_name", "get_phone", "user", "employer", "reason", "date_added")
    search_fields = ("user__first_name", "user__last_name", "user__username", "user__phone_number", "employer__name")
    ordering = ("user__first_name", "user__last_name", "user__phone_number",)  # Sorts list by phone number
    list_filter = ("employer",)  # ✅ Filter by employer in Django Admin

    autocomplete_fields = ["user"]

    def get_first_name(self, obj):
        return obj.user.first_name if obj.user else "N/A"
    get_first_name.admin_order_field = "user__first_name"
    get_first_name.short_description = "First Name"

    def get_last_name(self, obj):
        return obj.user.last_name if obj.user else "N/A"
    get_last_name.admin_order_field = "user__last_name"
    get_last_name.short_description = "Last Name"

    def get_phone(self, obj):
        return obj.user.phone_number if obj.user else "N/A"
    get_phone.admin_order_field = "user__phone_number"
    get_phone.short_description = "Phone Number"

    def get_employer(self, obj):
        return obj.employer.name if obj.employer else "N/A"
    get_employer.admin_order_field = "employer__name"
    get_employer.short_description = "Employer"


@admin.register(EmployerSMSTask)
class EmployerSMSTaskAdmin(admin.ModelAdmin):
    list_display = ('employer', 'task_name', 'is_enabled')  # Show employer & status
    list_filter = ('task_name', 'is_enabled')  # Filter by task and status
    search_fields = ('employer__name', 'task_name')  # Search by employer name
    list_editable = ('is_enabled',)  # ✅ Allow enabling/disabling directly from the list view


@admin.register(TenantApiKeys)
class TenantApiKeysAdmin(admin.ModelAdmin):
    list_display = ("employer", "account_sid", "phone_number", "sender_email", "status", "created_at")
    search_fields = ("employer__name", "service_name", "account_sid", "sender_email")


@admin.register(DocuSignTemplate)
class DocuSignTemplateAdmin(admin.ModelAdmin):
    list_display = ("template_name", "employer", "is_new_hire_template", "created_at")
    search_fields = ("template_name",)
    list_filter = ("employer", "is_new_hire_template",)


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "get_employers", "sendgrid_id", "include_in_report")
    search_fields = ("name", "sendgrid_id", "employers__name")
    list_filter = ("employers",)

    def get_employers(self, obj):
        """Display multiple employers as a comma-separated string."""
        return ", ".join([emp.name for emp in obj.employers.all()])

    get_employers.short_description = "Employers"


@admin.register(EmployerSettings)
class EmployerSettingsAdmin(admin.ModelAdmin):
    list_display = ("employer", "send_new_hire_file")
    list_filter = ("send_new_hire_file",)


@admin.register(Employer)
class EmployerAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "is_active", "verified_sender_email", "toggle_active_button"]
    actions = ["activate_selected", "deactivate_selected"]
    search_fields = ("name", "phone_number", "verified_sender_local", "verified_sender_email", "senior_contact_name")
    readonly_fields = ("verified_sender_email",)  # Prevent editing full email
    list_filter = ("created", "state_province", "country")

    def toggle_active_button(self, obj):
        """Add a button to toggle employer's active status."""
        if obj.is_active:
            return format_html('<a class="button" style="color:red;" href="/admin/user/employer/{}/toggle-active/">Deactivate</a>', obj.pk)
        return format_html('<a class="button" style="color:green;" href="/admin/user/employer/{}/toggle-active/">Activate</a>', obj.pk)

    toggle_active_button.short_description = "Toggle Active"

    def activate_selected(self, request, queryset):
        """Action to activate multiple employers at once."""
        queryset.update(is_active=True)
        messages.success(request, "Selected employers have been activated.")

    activate_selected.short_description = "Activate selected employers"

    def deactivate_selected(self, request, queryset):
        """Action to deactivate multiple employers at once."""
        queryset.update(is_active=False)
        messages.warning(request, "Selected employers have been deactivated.")

    deactivate_selected.short_description = "Deactivate selected employers"

    def get_urls(self):
        """Add a custom URL to toggle active status."""
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:pk>/toggle-active/",
                self.admin_site.admin_view(self.toggle_active),
                name="employer-toggle-active",
            ),
        ]
        return custom_urls + urls

    def toggle_active(self, request, pk):
        """Toggle employer's active status."""
        employer = Employer.objects.get(pk=pk)
        employer.is_active = not employer.is_active
        employer.save()

        if employer.is_active:
            self.message_user(request, f"Employer {employer.name} is now active.", messages.SUCCESS)
        else:
            self.message_user(request, f"Employer {employer.name} has been deactivated.", messages.WARNING)

        return redirect("/admin/user/employer/")



@admin.register(NewHireInvite)
class NewHireInviteAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "role", "employer", "created_at", "used", "invite_link_display")
    list_filter = ("employer", "role", "used")
    search_fields = ("name", "email", "employer__name")
    ordering = ("-created_at",)
    readonly_fields = ("token", "created_at", "invite_link_display")

    def invite_link_display(self, obj):
        return obj.get_invite_link()
    invite_link_display.short_description = "Invite Link"

    fieldsets = (
        (None, {"fields": ("name", "email", "role", "employer", "used")}),
        ("Invite Details", {"fields": ("token", "invite_link_display", "created_at")}),
    )


class EmployerRequestAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "phone_number", "status", "approve_button"]
    actions = ["approve_selected_requests"]

    def approve_button(self, obj):
        return format_html('<a class="button" href="/approve-employer/{}/">Approve</a>', obj.pk)
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
            messages.success(request, f"Successfully approved {approved_count} employer(s).")
        else:
            messages.warning(request, "No pending employer requests were selected.")

        return redirect("/admin/user/employerrequest/")

    approve_selected_requests.short_description = "Approve selected employer requests"


class SignedDocumentSingleUploadForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(is_active=True),
        label="Select User"
    )
    employer = forms.ModelChoiceField(
        queryset=Employer.objects.all(),
        label="Select Employer"
    )
    file = forms.FileField(
        label="Select File to Upload"
    )


@admin.register(SignedDocumentFile)
class SignedDocumentFileAdmin(admin.ModelAdmin):
    list_display = ("file_name", "user", "employer", "uploaded_at")
    change_list_template = "admin/signed_documents_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("upload-one/", self.admin_site.admin_view(self.upload_single_view), name="signed_document_upload_one"),
        ]
        return custom_urls + urls

    def upload_single_view(self, request):
        if request.method == "POST":
            form = SignedDocumentSingleUploadForm(request.POST, request.FILES)
            if form.is_valid():
                user = form.cleaned_data["user"]
                employer = form.cleaned_data["employer"]
                file = form.cleaned_data["file"]

                folder_name = uuid.uuid4().hex[:8]
                file_path = f"DOCUMENTS/{employer.name.replace(' ', '_')}/{folder_name}/{file.name}"

                upload_to_linode_object_storage(file, file_path)

                SignedDocumentFile.objects.create(
                    user=user,
                    employer=employer,
                    envelope_id=uuid.uuid4().hex[:10],
                    file_name=file.name,
                    file_path=file_path,
                )

                self.message_user(request, f"Successfully uploaded file for {user}.", level=messages.SUCCESS)
                return redirect("..")
        else:
            form = SignedDocumentSingleUploadForm()

        context = {
            "form": form,
        }
        return render(request, "admin/signed_documents_upload_one.html", context)
    

admin.site.register(EmployerRequest, EmployerRequestAdmin)
admin.site.register(Twimlmessages)
admin.site.register(BulkEmailSendgrid)
admin.site.register(Store, StoreAdmin)
admin.site.register(Incident, IncidentAdmin)
admin.site.register(MajorIncident, MajorIncidentAdmin)
admin.site.register(ProcessedDocsignDocument)
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(WhatsAppTemplate)
admin.site.register(Quiz, QuizAdmin)
admin.site.register(Answer)
admin.site.register(Question, QuestionAdmin)
admin.site.register(ExternalRecipient, ExternalRecipientAdmin)
admin.site.register(SMSOptOut, SMSOptOutAdmin)
