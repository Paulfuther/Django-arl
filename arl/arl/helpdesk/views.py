from django.shortcuts import render

from .models import HelpSection


def help_page(request):
    sections = HelpSection.objects.filter(is_active=True)
    return render(request, "helpdesk/help_page.html", {"sections": sections})
