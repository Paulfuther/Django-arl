from django.urls import path

from arl.incident.views import (IncidentCreateView, IncidentListView,
                                IncidentUpdateView, MajorIncidentCreateView,
                                MajorIncidentListView, MajorIncidentUpdateView,
                                Permission_Denied_View,
                                ProcessIncidentImagesView,
                                QueuedIncidentsListView,
                                generate_incident_pdf_email,
                                generate_major_incident_pdf, generate_pdf,
                                generate_pdf_web, send_incident_now,
                                mark_do_not_send, generate_restricted_pdf_web,
                                generate_restricted_incident_pdf_email,
                                htmx_edit_incident, incident_dashboard)

urlpatterns = [
    path("incident/", IncidentCreateView.as_view(), name="create_incident"),
    path("incident/dashboard/", incident_dashboard, name="incident_dashboard"),
    path("incident/<int:pk>/", IncidentUpdateView.as_view(),
         name="update_incident"),
    path("incident/edit/<int:pk>/", htmx_edit_incident, name="htmx_edit_incident"),
    path("major_incident/", MajorIncidentCreateView.as_view(),
         name="create_major_incident"),
    path("major_incident/<int:pk>/", MajorIncidentUpdateView.as_view(),
         name="update_major_incident"),
    path("process_images/", ProcessIncidentImagesView.as_view(),
         name="incident_upload"),
    path("generate_pdf/<int:incident_id>/", generate_pdf, name="generate_pdf"),
    path("generate_pdf_web/<int:incident_id>/", generate_pdf_web, name="generate_pdf_web"),
    path("generate_restricted_pdf_web/<int:incident_id>/",
         generate_restricted_pdf_web, name="generate_restricted_pdf_web"),
    path("generate_major_incident_pdf/<int:incident_id>/",
         generate_major_incident_pdf, name="generate_major_incident_pdf"),
    path("email-incident-pdf/<int:incident_id>",
         generate_incident_pdf_email, name="tester"),
    path("email-restricted-incident-pdf/<int:incident_id>",
         generate_restricted_incident_pdf_email, name="restricted_incident_pdf_email"), 
    path("incident_list/", IncidentListView.as_view(), name="incident_list"),
    path("major_incident_list/", MajorIncidentListView.as_view(),
         name="major_incident_list"),
    path("403/", Permission_Denied_View, name="permission_denied"),
    path('queued-incidents/', QueuedIncidentsListView.as_view(), name='queued_incidents_list'),
    path('send-now/<int:pk>/', send_incident_now, name='send_incident_now'),
    path('do-not-send/<int:pk>/', mark_do_not_send, name='mark_do_not_send'),

]

handler403 = "arl.incident.views.Permission_Denied_View"
