from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from import_export import fields
from import_export import fields as export_fields
from import_export import resources
from import_export.admin import ExportActionMixin
from arl.payroll.models import PayPeriod, StatutoryHoliday, CalendarEvent
from arl.dsign.models import DocuSignTemplate, ProcessedDocsignDocument
from arl.incident.models import Incident, MajorIncident
from arl.msg.models import (BulkEmailSendgrid, EmailTemplate, Twimlmessages,
                            UserConsent, WhatsAppTemplate)
from arl.quiz.models import Answer, Question, Quiz, SaltLog

from .models import CustomUser, Employer, ExternalRecipient, Store, UserManager

# fields = list(UserAdmin.fieldsets)


class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'sendgrid_id', 'include_in_report')  # Display the checkbox
    list_editable = ('include_in_report',)  # Allow inline editing of the checkbox
    search_fields = ('name',)


class ExternalRecipientAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'company', 'email', 'group')
    search_fields = ('first_name', 'last_name', 'company', 'email',
                     'group__name')


class UserResource(resources.ModelResource):
    manager = export_fields.Field()
    whatsapp_consent = export_fields.Field()
    store = fields.Field(column_name="store", readonly=True)

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


class CustomUserAdmin(ExportActionMixin, UserAdmin):
    resource_class = UserResource
    # Customize the fields you want to display
    list_display = (
        "username",
        "email",
        "store",
        "phone_number",
        "last_login",
        "is_active",
        "get_groups",
        "get_consent",
    )
    list_filter = ("is_active", "groups")  # Add any filters you need

    # def has_delete_permission(self, request, obj=None):
    #    return False  # Disables the ability to delete users

    def get_groups(self, obj):
        return ", ".join([group.name for group in obj.groups.all()])

    get_groups.short_description = "Groups"

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


@admin.register(PayPeriod)
class PayPeriodAdmin(admin.ModelAdmin):
    list_display = ['start_date', 'end_date', 'gross_pay', 'net_pay', 'deductions']


@admin.register(StatutoryHoliday)
class StatutoryHolidayAdmin(admin.ModelAdmin):
    list_display = ['date', 'name', 'pay_period']


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ['date', 'event_type', 'description']


# UserAdmin.fieldsets = tuple(fields)
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
