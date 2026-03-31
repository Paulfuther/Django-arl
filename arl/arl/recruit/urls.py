from django.urls import path
from .views import (
    recruit_apply_view,
    recruit_thank_you_view,
    recruit_applicant_list_view,
    recruit_phone_verify_view
)

app_name = "recruit"

urlpatterns = [
    path("apply/", recruit_apply_view, name="apply"),
    path("thank-you/", recruit_thank_you_view, name="thank_you"),
    path("applicants/", recruit_applicant_list_view, name="applicant_list"),
    path("verify-phone/", recruit_phone_verify_view, name="verify_phone"),
]