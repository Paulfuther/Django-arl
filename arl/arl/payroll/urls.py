from django.urls import path
from arl.payroll.views import payroll_entry_view

urlpatterns = [
    path("payroll/<int:pay_period_id>/", payroll_entry_view, name="payroll_entry"),
]
