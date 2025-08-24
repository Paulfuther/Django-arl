from django.contrib import admin

# checks/admin.py
from .models import Checklist, ChecklistItem, ChecklistTemplate, ChecklistTemplateItem


class ChecklistTemplateItemInline(admin.TabularInline):
    model = ChecklistTemplateItem
    extra = 0


@admin.register(ChecklistTemplate)
class ChecklistTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_by", "created_at")
    inlines = [ChecklistTemplateItemInline]


class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 0


@admin.register(Checklist)
class ChecklistAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "status",
        "created_by",
        "submitted_by",
        "created_at",
        "submitted_at",
    )
    inlines = [ChecklistItemInline]
