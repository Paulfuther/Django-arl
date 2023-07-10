from django.urls import path
from .views import register
from .views import CheckPhoneNumberUniqueView
from .views import send_email_view

urlpatterns = [
    # ...
    path('', register, name='register'),
    path('check_phone_number_unique/', CheckPhoneNumberUniqueView.as_view(), name='check_phone_number_unique'),
    path('send-email/', send_email_view, name='send_email')
    # ...

]

