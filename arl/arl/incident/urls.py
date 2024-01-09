from django.urls import path

from arl.incident.views import (
    IncidentCreateView,
    IncidentListView,
    IncidentUpdateView,
    Permission_Denied_View,
    ProcessIncidentImagesView,
    generate_incident_pdf_email,
    generate_pdf,
)

urlpatterns = [
    path("incident/", IncidentCreateView.as_view(), name="create_incident"),
    path("incident/<int:pk>/", IncidentUpdateView.as_view(), name="update_incident"),
    path("process_images/", ProcessIncidentImagesView.as_view(), name="incident_upload"),
    path("generate-pdf/<int:incident_id>/", generate_pdf, name="generate_pdf"),
    path("email-incident-pdf/<int:incident_id>", generate_incident_pdf_email, name="tester"),
    path("incident_list/", IncidentListView.as_view(), name="incident_list"),
    path("403/", Permission_Denied_View, name="permission_denied"),
]

handler403 = "arl.incident.views.Permission_Denied_View"
