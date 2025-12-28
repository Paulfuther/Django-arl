# carwash/urls.py
from django.urls import path
from .views import carwash_status_view, carwash_status_list_view, carwash_status_report


urlpatterns = [
    path("carwash-status/", carwash_status_view, name="carwash_status"),
    path("carwash-status-list/", carwash_status_list_view, name="carwash_status_list"),
    path("carwash-status-report/", carwash_status_report, name="carwash_status_report"),
]
