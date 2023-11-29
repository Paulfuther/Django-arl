import json
import logging

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from arl.dsign.helpers import get_docusign_envelope, list_all_docusign_envelopes
from arl.tasks import create_docusign_envelope_task, process_docusign_webhook

from .forms import NameEmailForm

logger = logging.getLogger(__name__)


def create_envelope(request):
    if request.method == "POST":
        form = NameEmailForm(request.POST)
        if form.is_valid():
            d_name = form.cleaned_data["name"]
            d_email = form.cleaned_data["email"]
            ds_template = form.cleaned_data.get("template_id")
            # print(ds_template)
            envelope_args = {
                "signer_email": d_email,
                "signer_name": d_name,
                "template_id": ds_template,
            }
            create_docusign_envelope_task.delay(envelope_args)

            messages.success(
                request,
                "Thank you for registering. Please check your email for your New Hire File from Docusign.",
            )
            return redirect("home")
    else:
        form = NameEmailForm()
        return render(request, "dsign/name_email_form.html", {"form": form})
        # i cut here.


@csrf_exempt  # In production, use proper CSRF protection.
def docusign_webhook(request):
    if request.method == "POST":
        try:
            payload = json.loads(request.body.decode("utf-8"))
            process_docusign_webhook.delay(payload)
            return JsonResponse({"message": "Webhook processed successfully"})

        except json.JSONDecodeError:
            logger.error("Invalid JSON payload")
            return JsonResponse({"error": "Invalid JSON payload"}, status=400)

        except Exception as e:
            logger.error(f"Error processing DocuSign webhook: {str(e)}")
            return JsonResponse(
                {"error": f"Error processing DocuSign webhook: {str(e)}"}, status=500
            )

    else:
        return JsonResponse({"error": "Only POST requests are allowed"}, status=405)


def retrieve_docusign_envelope(request):
    try:
        get_docusign_envelope()
        messages.success(request, "Docusign Document Has Been Emailed.")
    except Exception as e:
        messages.error(request, f"Process failed: {str(e)}")

    return redirect('home')


def list_docusign_envelope(request):
    list_all_docusign_envelopes()
    return HttpResponse("Process completed successfully.")