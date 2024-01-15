from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from arl.helpers import download_from_s3, list_s3_objects


@login_required(login_url="login")
def access_s3(request):
    folder_name = "SITEINCIDENT/a0061TerryFuther/INCIDENTPDF"
    filtered_keys = list_s3_objects(folder_name)
    # print(filtered_keys)
    return render(request, "bucket/s3_object.html", {"filtered_keys": filtered_keys})


@login_required(login_url="login")
def download_s3(request, key):
    # print("madeit" ,key)
    return download_from_s3(key)
