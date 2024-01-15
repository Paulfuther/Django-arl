from django.urls import path

from arl.bucket.views import access_s3, download_s3


urlpatterns = [
    path("list-s3-objects/", access_s3, name="list_s3_objects"),
    path('s3_download/<str:key>/', download_s3, name='download_from_s3'),
]
