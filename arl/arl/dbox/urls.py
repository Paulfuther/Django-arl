from django.urls import path

from arl.dbox.views import (
    delete_file,
    download_file,
    list_files,
    list_folder_contents,
    list_folders,
    upload_file,
    use_dropbox,
    view_folder,
)

urlpatterns = [
    path("use_dropbox/", use_dropbox, name="new token"),
    path("list_folders/", list_folders, name="list_folders"),
    path("list_files/", list_files, name="list_files"),
    path("list_files/<str:path>/", list_files, name="list_files"),
    path("view_folder/", view_folder, name="view_folder"),
    path("list_folder_contents/<path:path>/", list_folder_contents, name="list_folder_contents"),
    path("download_file/", download_file, name="download_file"),
    path("upload_file/", upload_file, name="upload_file"),
    path("delete_file/", delete_file, name="delete_file")
]
