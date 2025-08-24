from django.urls import path

from . import views
from .views import (
    ProcessSaltLogImagesView,
    SaltLogCreateView,
    SaltLogListView,
    SaltLogUpdateView,
    UploadChecklistItemPhotoView
)

urlpatterns = [
    path("list/", views.quiz_list, name="quiz_list"),
    path("create/", views.create_quiz, name="create_quiz"),
    path("take/<int:quiz_id>/", views.take_quiz, name="take_quiz"),
    path("create-salt-log/", SaltLogCreateView.as_view(), name="create_salt_log"),
    path("incident/<int:pk>/", SaltLogUpdateView.as_view(), name="salt_log_update"),
    path("salt-log-list/", SaltLogListView.as_view(), name="salt_log_list"),
    path(
        "log-process-images/",
        ProcessSaltLogImagesView.as_view(),
        name="salt_log_upload",
    ),
    path("checklists/", views.checklist_dashboard, name="checklist_dashboard"),
    path("templates/new/", views.template_create, name="template_create"),
    path("templates/<int:pk>/", views.template_detail, name="template_detail"),
    path("templates/<int:pk>/edit/", views.template_edit, name="template_edit"),
    path(
        "start/<int:template_id>/",
        views.checklist_from_template,
        name="checklist_from_template",
    ),
    path("<slug:slug>/edit/", views.checklist_edit, name="checklist_edit"),
    path("<slug:slug>/", views.checklist_detail, name="checklist_detail"),
    path(
        "checklists/<slug:slug>/items/<uuid:item_uuid>/upload/",
        UploadChecklistItemPhotoView.as_view(),
        name="upload_checklist_item_photo",
    ),
    # path('saltlog-pdf/', views.generate_salt_log_pdf,
    #     name='generate_saltlog_pdf'),
]
