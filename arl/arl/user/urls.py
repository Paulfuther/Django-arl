from django.urls import path

from .views import (CheckPhoneNumberUniqueView, register, send_bulk_sms,
                    sms_form)

urlpatterns = [
    path('', register, name='register'),
    path('check_phone_number_unique/', CheckPhoneNumberUniqueView.as_view(),
         name='check_phone_number_unique'),
    path('sms_form/', sms_form, name='sms_form'),
    path('bulk_sms/', send_bulk_sms, name='Bulk SMS')
]