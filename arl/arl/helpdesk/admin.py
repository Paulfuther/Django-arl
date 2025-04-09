from django.contrib import admin

from .models import HelpSection


@admin.register(HelpSection)
class HelpSectionAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active")
    list_filter = ("is_active",)
    search_fields = ("title", "content")
