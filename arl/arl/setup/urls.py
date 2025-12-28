from django.urls import path
from arl.setup.views import (
    trigger_error,
    stripe_webhook,
    payment_success,
    payment_cancel,
    approve_employer,
    EmployerRegistrationView,
)

urlpatterns = [
    path("trigger-error/", trigger_error, name="trigger_error"),
    path("stripe/webhook/", stripe_webhook, name="stripe-webhook"),
    path("payment-success/", payment_success, name="payment_success"),
    path("payment-cancel/", payment_cancel, name="payment_cancel"),
    path("approve-employer/<int:pk>/", approve_employer, name="approve_employer"),
    path(
        "register-employer/",
        EmployerRegistrationView.as_view(),
        name="register_employer",
    ),
]
