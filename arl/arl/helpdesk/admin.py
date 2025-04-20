from django.contrib import admin

from .models import HelpSection, HelpCategory


@admin.register(HelpCategory)
class HelpCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(HelpSection)
class HelpSectionAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("title", "content")
