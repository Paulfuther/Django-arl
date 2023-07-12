from django.urls import path

from .views import CheckPhoneNumberUniqueView, register

urlpatterns = [
    # ...
    path('', register, name='register'),
    path('check_phone_number_unique/', CheckPhoneNumberUniqueView.as_view(),
         name='check_phone_number_unique'),
    #path('send_email_test', send_email_test, name='send_oneoff_email'),
    # ...

]

