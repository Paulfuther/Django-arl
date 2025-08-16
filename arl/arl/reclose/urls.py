from django.urls import path
from .views import rec_close_success
from .views import rec_close_create_view


urlpatterns = [
    path('reclose/new/', rec_close_create_view, name="create_reclose"),
    path('recclose/success/', rec_close_success, name='rec_close_success'),
]