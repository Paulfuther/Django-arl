from django.shortcuts import render
from .models import HelpCategory


def help_center(request):
    categories = HelpCategory.objects.filter(is_active=True)

    # Force "Getting Started" to the top
    categories = sorted(
        categories,
        key=lambda c: (0 if c.name.lower() == "getting started" else 1, c.name.lower()),
    )

    return render(request, "helpdesk/help_center.html", {"categories": categories})
