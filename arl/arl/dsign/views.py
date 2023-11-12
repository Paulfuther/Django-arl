import json

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render

from .forms import NameEmailForm
from arl.tasks import create_docusign_envelope_task
# Create your views here.


def create_newhire(request):
    if request.method == "POST":
        form = NameEmailForm(request.POST)
        if form.is_valid():
            d_name = form.cleaned_data["name"]
            d_email = form.cleaned_data["email"]
            # Do something with the collected data, e.g., save to database
            # Return a success message or redirect to another page
            return render(request, "success.html", {"name": d_name, "email": d_email})
    else:
        form = NameEmailForm()
    return render(request, "name_email_form.html", {"form": form})


def create_envelope(request):
    if request.method == "POST":
        form = NameEmailForm(request.POST)
        if form.is_valid():
            d_name = form.cleaned_data["name"]
            d_email = form.cleaned_data["email"]
            ds_template = settings.DOCUSIGN_TEMPLATE_ID
            # print(ds_template)
            envelope_args = {
                "signer_email": d_email,
                "signer_name": d_name,
                "template_id": ds_template,
            }
            create_docusign_envelope_task.delay(envelope_args)

            messages.success(request, 'Thank you for registering. Please check your email for your New Hire File from Docusign.')
            return redirect('home')
    else:
        form = NameEmailForm()
        return render(request, "dsign/name_email_form.html", {"form": form})
        # i cut here.


def docusign_webhook(request):
    if request.method == "POST":
        data = json.loads(request.body)
        print(data)
        # Extract envelope status and signer information from the data
        envelope_status = data["envelopeStatus"]
        signer_email = data["signerEmail"]
        signer_name = data["signerName"]
        # Send a Twilio SMS if the envelope status changes to completed
        if envelope_status == "Completed":
            print("Email :", signer_email, "Name :", signer_name)

            return JsonResponse({"message": "Twilio SMS sent."})

    return JsonResponse({"message": "Invalid request."})
