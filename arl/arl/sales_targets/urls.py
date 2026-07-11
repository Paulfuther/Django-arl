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
    # path(
    #    "dashboard/<int:period_id>/ai-coaching/",
    #    views.ai_sales_coaching_dashboard,
    #    name="ai_sales_coaching_dashboard",
    # ),
    path(
        "import/",
        views.sales_import_upload,
        name="sales_import_upload",
    ),
    path(
        "import/<uuid:batch_id>/preview/",
        views.sales_import_preview,
        name="sales_import_preview",
    ),
    path(
        "import/<uuid:batch_id>/confirm/",
        views.sales_import_confirm,
        name="sales_import_confirm",
    ),
    path(
        "import/<uuid:batch_id>/complete/",
        views.sales_import_complete,
        name="sales_import_complete",
    ),
    path(
        "import/<uuid:batch_id>/cancel/",
        views.sales_import_cancel,
        name="sales_import_cancel",
    ),
]
