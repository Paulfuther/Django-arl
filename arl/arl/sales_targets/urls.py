from django.urls import path

from . import views

app_name = "sales_targets"

urlpatterns = [
    path("", views.index, name="index"),
    path(
        "dashboard/<int:period_id>/",
        views.sales_target_dashboard,
        name="sales_target_dashboard",
    ),
]
