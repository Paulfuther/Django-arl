from django.urls import path
from arl.payroll.views import payroll_calendar_view, payroll_entry_view

urlpatterns = [
    path('calendar/', payroll_calendar_view, name='payroll_calendar'),
    path('entry/', payroll_entry_view, name='payroll_entry'),
]