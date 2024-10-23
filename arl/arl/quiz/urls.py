from django.urls import path
from . import views
from .views import (SaltLogCreateView, ProcessSaltLogImagesView,
                    SaltLogListView, SaltLogUpdateView)

urlpatterns = [
    path('list/', views.quiz_list, name='quiz_list'),
    path('create/', views.create_quiz, name='create_quiz'),
    path('take/<int:quiz_id>/', views.take_quiz, name='take_quiz'),
    path('create-salt-log/', SaltLogCreateView.as_view(),
         name='create_salt_log'),
    path("incident/<int:pk>/", SaltLogUpdateView.as_view(),
         name="salt_log_update"),
    path("salt-log-list/", SaltLogListView.as_view(), name="salt_log_list"),
    path("log-process-images/", ProcessSaltLogImagesView.as_view(),
         name="salt_log_upload"),
]
