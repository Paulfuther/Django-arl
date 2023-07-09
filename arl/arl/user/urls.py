from django.urls import path
from .views import register
from .views import CheckPhoneNumberUniqueView

urlpatterns = [
    # ...
    path('', register, name='register'),
    path('check_phone_number_unique/', CheckPhoneNumberUniqueView.as_view(), name='check_phone_number_unique'),
    # ...

]

