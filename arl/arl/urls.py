
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", include("arl.user.urls")),
]
handler403 = 'arl.views.error_403'
handler500 = 'arl.views.error_500'
