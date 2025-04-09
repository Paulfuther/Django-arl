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
    path("", include("arl.bucket.urls")),
    path("quiz/", include("arl.quiz.urls")),
    path("", include("arl.payroll.urls")),
    path("", include("arl.carwash.urls")),
    path("", include("arl.setup.urls")),
    path("", include("arl.helpdesk.urls"))
]


handler403 = "arl.views.error_403"
handler500 = "arl.views.error_500"
handler405 = "arl.views.error_405"
