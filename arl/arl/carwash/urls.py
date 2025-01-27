# carwash/urls.py
from django.urls import path
from .views import carwash_status_view, carwash_status_list_view

urlpatterns = [
    path('carwash-status/', carwash_status_view, name='carwash_status'),
    path('carwash-status-list/', carwash_status_list_view, name='carwash_status_list'),
]