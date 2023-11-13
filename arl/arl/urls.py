from django.contrib import admin
from django.urls import include, path

from arl.user.views import CustomAdminLoginView

admin.site.login = CustomAdminLoginView.as_view()

urlpatterns = [
    path("custom-admin-login/", CustomAdminLoginView.as_view(), name="custom_admin_login"),
    path("admin/", admin.site.urls),
    path("", include("arl.user.urls")),
    path("", include("arl.dbox.urls")),
    path("", include("arl.incident.urls")),
    path("", include("arl.dsign.urls")),
    path("", include("arl.msg.urls")),
]

handler403 = "arl.views.error_403"
handler500 = "arl.views.error_500"
