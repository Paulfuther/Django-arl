from django.urls import path

from . import views

app_name = "sales_targets"

urlpatterns = [
    path("", views.index, name="index"),
    path(
    "dashboard/",
    views.sales_target_dashboard_selector,
    name="sales_target_dashboard_selector",
    ),

    path(
        "dashboard/<int:period_id>/",
        views.sales_target_dashboard,
        name="sales_target_dashboard",
    ),
    path(
        "dashboard/<int:period_id>/export-summary/",
        views.export_sales_target_summary_dashboard,
        name="export_sales_target_summary_dashboard",
    ),

    path(
        "dashboard/<int:period_id>/export-management/",
        views.export_sales_target_management_dashboard,
        name="export_sales_target_management_dashboard",
    ),
    #path(
    #    "dashboard/<int:period_id>/ai-coaching/",
    #    views.ai_sales_coaching_dashboard,
    #    name="ai_sales_coaching_dashboard",
    #),
    ]
