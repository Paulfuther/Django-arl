
from django.urls import path

from arl.dsign.views import create_envelope

from .views import (CheckPhoneNumberUniqueView, check_verification, home_view,
                    login_view, logout_view, register, request_verification,
                    sms_form)

urlpatterns = [
    path('', login_view, name='login'),
    path('register', register, name='register'),
    path('check_phone_number_unique/', CheckPhoneNumberUniqueView.as_view(),
         name='check_phone_number_unique'),
    path('request-verification/', request_verification, name='request_verification'),
    path('check-verification/', check_verification, name='check_verification'),
    path('sms_form/', sms_form, name='sms_form'),
    path('docsign/', create_envelope, name='Create Envelope'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('home/', home_view, name='home')
]
