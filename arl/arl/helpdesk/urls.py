from django.urls import path

from .views import help_page

urlpatterns = [
    path("help/", help_page, name="help_page"),
]
