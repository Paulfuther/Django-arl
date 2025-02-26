from datetime import datetime

from django import forms
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from import_export import fields
from import_export import fields as export_fields
from import_export import resources
from import_export.admin import ExportActionMixin
from django.utils.html import strip_tags
from arl.carwash.models import CarwashStatus
from arl.dsign.models import DocuSignTemplate, ProcessedDocsignDocument
from arl.incident.models import Incident, MajorIncident
from arl.msg.models import (BulkEmailSendgrid, EmailTemplate, Twimlmessages,
                            UserConsent, WhatsAppTemplate)
from arl.msg.tasks import EmployerSMSTask
# from arl.payroll.models import CalendarEvent, PayPeriod, StatutoryHoliday
from arl.quiz.models import Answer, Question, Quiz, SaltLog

from .models import (CustomUser, DocumentType, EmployeeDocument, Employer,
                     ExternalRecipient, SMSOptOut, Store, UserManager)
from arl.setup.models import TenantApiKeys


class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'sendgrid_id', 'include_in_report')  # Display the checkbox
    list_editable = ('include_in_report',)  # Allow inline editing of the checkbox
    search_fields = ('name',)


class ExternalRecipientAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'company', 'email', 'group')
    search_fields = ('first_name', 'last_name', 'company', 'email',
                     'group__name')


# This calss is used for exporting
class UserResource(resources.ModelResource):
    manager = export_fields.Field()
    whatsapp_consent = export_fields.Field()
    store = fields.Field(column_name="store", readonly=True)
    all_docusign_templates = fields.Field(column_name="Docusign Documents", attribute="all_docusign_templates")

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
            "all_docusign_templates",
        )
        export_order = (
            "store",
            "username",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "manager",
            "whatsapp_consent",
            "sin",
            "all_docusign_templates",
        )

    def dehydrate_manager(self, custom_user):
        # Assuming a reverse ForeignKey from
        # UserManager to CustomUser as 'managed_users'
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

    def dehydrate_store(self, obj):
        try:
            store_name = obj.store.number if obj.store else "No Store Assigned"
            # print(f"Exporting store for user {obj.username}: {store_name}")
            return store_name
        except Exception as e:
            # print(f"Error exporting store for user {obj.username}: {e}")
            raise e

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
    # Customize the fields you want to display
    inlines = [ProcessedDocusignDocumentInline]
    list_display = (
        "username",
        "email",
        "store",
        'employer',
        "phone_number",
        "sin",
        "last_login",
        "is_active",
        "get_groups",
        "get_consent",
        "sin_expiration_date",
        "work_permit_expiration_date",
        "all_docusign_templates",
    )
    list_filter = ("is_active", "groups", 'sin_expiration_date', 'work_permit_expiration_date', SINFirstDigitFilter)
    search_fields = ("username", "email", "phone_number", "sin")
    list_editable = ('sin_expiration_date', 'work_permit_expiration_date')
    list_per_page = 15
    # def has_delete_permission(self, request, obj=None):
    #    return False  # Disables the ability to delete users

    def get_groups(self, obj):
        return ", ".join([group.name for group in obj.groups.all()])

    get_groups.short_description = "Groups"

    def expandable_groups(self, obj):
        """Creates an expandable section for groups."""
        groups = ", ".join([group.name for group in obj.groups.all()]) or "No Groups"
        return format_html(
            '<button class="expand-btn" onclick="toggleGroups(this)">Show Groups</button>'
            '<div class="group-list" style="display: none; padding: 5px; border: 1px solid #ddd; background: #f9f9f9;">{}</div>',
            groups
        )

    expandable_groups.short_description = "Groups"

    class Media:
        js = ('/admin/custom_admin.js',)

    def all_docusign_templates(self, obj):
        """Display all template names for a user in a neat format."""
        templates = ProcessedDocsignDocument.objects.filter(user=obj).values_list("template_name", flat=True)

        if not templates:
            return "No Documents"

        # Convert None values to empty strings
        formatted_templates = "<br>".join(filter(None, templates))

        return format_html(formatted_templates)  # Ensure HTML is rendered correctly

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
        # Ensure 'phone_number' is saved when creating/updating a user
        obj.phone_number = form.cleaned_data.get("phone_number", "")
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
    list_display = ("get_first_name", "get_last_name", "get_phone", "user", "reason", "date_added")
    search_fields = ("user__first_name", "user__last_name", "user__username", "user__phone_number")
    ordering = ("user__first_name", "user__last_name", "user__phone_number",)  # Sorts list by phone number

    # Enable autocomplete search for the user field
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


@admin.register(EmployerSMSTask)
class EmployerSMSTaskAdmin(admin.ModelAdmin):
    list_display = ('employer', 'task_name', 'is_enabled')  # Show employer & status
    list_filter = ('task_name', 'is_enabled')  # Filter by task and status
    search_fields = ('employer__name', 'task_name')  # Search by employer name
    list_editable = ('is_enabled',)  # ✅ Allow enabling/disabling directly from the list view


@admin.register(TenantApiKeys)
class TenantApiKeysAdmin(admin.ModelAdmin):
    list_display = ("employer", "service_name", "account_sid", "phone_number", "sender_email", "status", "created_at")
    search_fields = ("employer__name", "service_name", "account_sid", "sender_email")
    list_filter = ("service_name", "status")


admin.site.register(Employer)
admin.site.register(Twimlmessages)
admin.site.register(BulkEmailSendgrid)
admin.site.register(Store, StoreAdmin)
admin.site.register(Incident, IncidentAdmin)
admin.site.register(MajorIncident, MajorIncidentAdmin)
admin.site.register(EmailTemplate)
admin.site.register(DocuSignTemplate)
admin.site.register(ProcessedDocsignDocument)
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(WhatsAppTemplate)
admin.site.register(Quiz, QuizAdmin)
admin.site.register(Answer)
admin.site.register(Question, QuestionAdmin)
admin.site.register(ExternalRecipient, ExternalRecipientAdmin)
admin.site.register(SMSOptOut, SMSOptOutAdmin)
