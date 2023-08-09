
from django.urls import path

from arl.dsign.views import create_envelope, docusign_webhook
from arl.dbox.views import (list_folders, list_files, view_folder, list_folder_contents,
                            download_file, upload_file, delete_file)
from .views import (CheckPhoneNumberUniqueView, check_verification, home_view,
                    login_view, logout_view, register, request_verification,
                    sms_form)

urlpatterns = [
    path('', login_view, name='login'),
    path('register', register, name='register'),
    path('check_phone_number_unique/', CheckPhoneNumberUniqueView.as_view(),
         name='check_phone_number_unique'),
    path('request-verification/', request_verification, name='request_verification'),
    path('check-verification/', check_verification, name='check_verification'),
    path('sms_form/', sms_form, name='sms_form'),
    path('docsign/', create_envelope, name='Create Envelope'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('home/', home_view, name='home'),
    path('list_folders/', list_folders, name='list_folders'),
    path('list_files/', list_files, name='list_files'),
    path('list_files/<str:path>/', list_files, name='list_files'),
    path('view_folder/', view_folder, name='view_folder'),
    path('list_folder_contents/<path:path>/', list_folder_contents, name='list_folder_contents'),
    path('download_file/', download_file, name='download_file'),
    path('docusign-webhook/', docusign_webhook, name='webhook'),
    path('upload_file/', upload_file, name='upload_file'),
    path('delete_file/', delete_file, name='delete_file'),
]
