import json

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render

from .forms import NameEmailForm
from arl.tasks import create_docusign_envelope_task

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
    payload = json.loads(request.body.decode('utf-8'))

    # Extract necessary information from the payload
    if 'data' in payload and 'envelopeSummary' in payload['data']:
        envelope_summary = payload['data']['envelopeSummary']
        status = envelope_summary.get('status')

        if status == 'sent':
            # Document sent to new hire
            send_sms_to_hr('Document sent to new hire. Check your email.')

        elif status == 'completed':
            # Document signed
            send_sms_to_hr('Document signed by new hire. Check your email.')

            # Retrieve the document file
            document_id = envelope_summary.get('documents')[0].get('documentId')
            file_url = f'https://demo.docusign.net/restapi/v2.1/accounts/{YOUR_ACCOUNT_ID}/envelopes/{envelope_summary["envelopeId"]}/documents/{document_id}'
            
            # Email the document to HR
            send_email_to_hr(file_url)

    return JsonResponse({'message': 'Webhook processed successfully'})


