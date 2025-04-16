from django.urls import path

from .views import help_center

urlpatterns = [
    path("help/", help_center, name="help_page"),
]
