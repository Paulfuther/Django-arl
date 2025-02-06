from django.contrib.auth import views as auth_views
from django.urls import path
from arl.setup.views import trigger_error



urlpatterns = [
    path("trigger-error/", trigger_error, name="trigger_error"),
]