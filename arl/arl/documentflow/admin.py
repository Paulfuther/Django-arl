from django.contrib import admin
from .models import DocumentFlow, DocumentFlowStep, SentDocuSignEnvelope


class DocumentFlowStepInline(admin.TabularInline):
    model = DocumentFlowStep
    extra = 1


@admin.register(DocumentFlow)
class DocumentFlowAdmin(admin.ModelAdmin):
    list_display = ("name", "employer", "is_active", "is_default", "created_at")
    list_filter = ("employer", "is_active", "is_default")
    search_fields = ("name", "employer__name")
    inlines = [DocumentFlowStepInline]


@admin.register(DocumentFlowStep)
class DocumentFlowStepAdmin(admin.ModelAdmin):
    list_display = (
        "flow",
        "step_order",
        "template",
        "label",
        "is_required",
        "is_active",
    )
    list_filter = ("flow__employer", "is_required", "is_active")
    search_fields = ("flow__name", "template__name", "label")
    ordering = ("flow", "step_order")


@admin.register(SentDocuSignEnvelope)
class SentDocuSignEnvelopeAdmin(admin.ModelAdmin):
    list_display = (
        "template_name",
        "user",
        "employer",
        "status",
        "sent_at",
        "completed_at",
    )
    list_filter = ("status", "employer")
    search_fields = ("template_name", "envelope_id", "user__first_name", "user__last_name", "user__email")