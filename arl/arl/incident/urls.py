from django.urls import path

from arl.incident.views import (
    IncidentCreateView,
    IncidentListView,
    IncidentUpdateView,
    ProcessIncidentImagesView,
    generate_pdf,
)

urlpatterns = [
    path("incident/", IncidentCreateView.as_view(), name="create_incident"),
    path("incident/<int:pk>/", IncidentUpdateView.as_view(),
         name="update_incident"),
    path(
        "process_images/", ProcessIncidentImagesView.as_view(),
        name="incident_upload"
    ),
    path("generate-pdf/<int:incident_id>/", generate_pdf, name="generate_pdf"),
    path("incident_list/", IncidentListView.as_view(), name="incident_list"),
]
