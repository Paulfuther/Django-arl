from django.urls import path

from arl.dsign.views import create_envelope

from .views import (CheckPhoneNumberUniqueView, check_verification, register,
                    request_verification, sms_form)

urlpatterns = [
    path('', register, name='register'),
    path('check_phone_number_unique/', CheckPhoneNumberUniqueView.as_view(),
         name='check_phone_number_unique'),
    path('request-verification/', request_verification, name='request_verification'),
    path('check-verification/', check_verification, name='check_verification'),
    path('sms_form/', sms_form, name='sms_form'),
    path('docsign/', create_envelope, name='Create Envelope')
]
