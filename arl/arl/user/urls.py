from django.urls import path

from .views import CheckPhoneNumberUniqueView, register, send_bulk_sms, sms_form, request_verification, check_verification, my_view


urlpatterns = [
    path('', register, name='register'),
    path('check_phone_number_unique/', CheckPhoneNumberUniqueView.as_view(),
         name='check_phone_number_unique'),
    path('request-verification/', request_verification, name='request_verification'),
    path('check-verification/', check_verification, name='check_verification'),
    path('sms_form/', sms_form, name='sms_form'),
    path('bulk_sms/', send_bulk_sms, name='Bulk SMS'),
    path('add/', my_view, name='Add')
]