from django.urls import path
from . import views

urlpatterns = [
    path('list/', views.quiz_list, name='quiz_list'),
    path('create/', views.create_quiz, name='create_quiz'),
    path('take/<int:quiz_id>/', views.take_quiz, name='take_quiz'),
]
