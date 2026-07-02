from django.urls import path
from . import views

app_name = "sales_targets"

urlpatterns = [
    path("", views.index, name="index"),
]