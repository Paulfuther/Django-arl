import json

from django.http import JsonResponse
from django.shortcuts import render
from docusign_esign import (ApiClient, EnvelopeDefinition, EnvelopesApi,
                            RecipientEmailNotification, SignerAttachment,
                            TemplateRole)

from .forms import NameEmailForm
from .helpers import get_access_token
from django.conf import settings
# Create your views here.


def create_newhire(request):
    if request.method == 'POST':
        form = NameEmailForm(request.POST)
        if form.is_valid():
            d_name = form.cleaned_data['name']
            d_email = form.cleaned_data['email']
            # Do something with the collected data, e.g., save to database
            # Return a success message or redirect to another page
            return render(request, 'success.html', {'name': d_name, 'email': d_email})
    else:
        form = NameEmailForm()
    return render(request, 'name_email_form.html', {'form': form})


def create_envelope(request):
    if request.method == 'POST':
        form = NameEmailForm(request.POST)
        if form.is_valid():
            d_name = form.cleaned_data['name']
            d_email = form.cleaned_data['email']
            # print(d_name, d_email)
            access_token = get_access_token()
            access_token = access_token.access_token
            ds_template = settings.DOCUSIGN_TEMPLATE_ID
            # print(ds_template)
            envelope_args = {
                "signer_email": d_email,
                "signer_name": d_name,
                "template_id": ds_template
            }

            args = {
                "base_path": settings.DOCUSIGN_BASE_PATH,
                "ds_access_token": access_token,
                "account_id": settings.DOCUSIGN_ACCOUNT_ID,
                "envelope_args": envelope_args
            }
            #print(args)

            # Specify your webhook URL where you want to receive the event notifications
            webhook_url = "https://www.paulfuther.com/docusign-webhook"

            # Construct the eventNotification
            event_notification = {
                    "URL": webhook_url,
                    "loggingEnabled": "true",
                    "requireAcknowledgment": "true",
                    "useSoapInterface": "false",
                    "includeCertificateWithSoap": "false",
                    "signMessageWithX509Cert": "false",
                    "includeDocuments": "true",
                    "includeEnvelopeVoidReason": "true",
                    "includeTimeZone": "true",
                    "includeSenderAccountAsCustomField": "true",
                    "includeDocumentFields": "true",
                    "includeCertificateOfCompletion": "true",
                    "envelopeEvents": [
                        {"envelopeEventStatusCode": "sent"},
                        {"envelopeEventStatusCode": "delivered"},
                        {"envelopeEventStatusCode": "completed"},
                        {"envelopeEventStatusCode": "declined"},
                        {"envelopeEventStatusCode": "voided"}
                    ],
                    "recipientEvents": [
                        {"recipientEventStatusCode": "Sent"},
                        {"recipientEventStatusCode": "Delivered"},
                        {"recipientEventStatusCode": "Completed"},
                        {"recipientEventStatusCode": "Declined"},
                        {"recipientEventStatusCode": "AuthenticationFailed"},
                        {"recipientEventStatusCode": "AutoResponded"}
                    ]
                }

            email_subject = f"{d_name} - {'New Hire File'}"
            # print(email_subject)
            # Create the envelope definition
            envelope_definition = EnvelopeDefinition(
                status="sent",  # requests that the envelope be created and sent.
                template_id=envelope_args['template_id'],
                eventNotification=event_notification,
                auto_navigation=False
            )

            # Create the signer role
            signer = TemplateRole(
                email=envelope_args['signer_email'],
                name=envelope_args['signer_name'],
                role_name='GSA',
                email_notification=RecipientEmailNotification(
                        email_subject=email_subject
                )
            )

            attachment_tab1 = SignerAttachment(
                    anchor_string="Upload Photo ID picture",
                    anchor_x_offset="0",
                    anchor_y_offset="0",
                    anchor_units="inches",
                    tab_label="ID_Image1",
                    optional="false",
            )

            attachment_tab2 = SignerAttachment(
                    anchor_string="Upload SIN picture",
                    anchor_x_offset="0",
                    anchor_y_offset="0",
                    anchor_units="inches",
                    tab_label="ID_Image2",
                    optional="false"
                )

            attachment_tab3 = SignerAttachment(
                    anchor_string="/void ch/",
                    anchor_x_offset="0",
                    anchor_y_offset="0",
                    anchor_units="inches",
                    tab_label="ID_Image3",
                    optional="false"
                )
            # Add the SignHere tab to the signer role
            signer.tabs = {
                "signerAttachmentTabs": [attachment_tab1, attachment_tab2, attachment_tab3]
            }

            # Add the TemplateRole objects to the envelope object
            envelope_definition.template_roles = [signer]
            api_client = ApiClient()
            api_client.host = settings.DOCUSIGN_API_CLIENT_HOST
            # print(api_client.host)
            # print(settings.DOCUSIGN_ACCOUNT_ID)
            api_client.set_default_header("Authorization", "Bearer " + access_token)
            # print(api_client)
            envelope_api = EnvelopesApi(api_client)
            # print(envelope_api)
            try:
                results = envelope_api.create_envelope(settings.DOCUSIGN_ACCOUNT_ID,
                                                       envelope_definition=envelope_definition)
                envelope_id = results.envelope_id
                return JsonResponse({'envelope_id': envelope_id})
            except Exception as e:
                print("error")
                return JsonResponse({'error': str(e)}), 500
    else:
        form = NameEmailForm()
        return render(request, 'dsign/name_email_form.html', {'form': form})


def docusign_webhook(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        print(data)
        # Extract envelope status and signer information from the data
        envelope_status = data['envelopeStatus']
        signer_email = data['signerEmail']
        signer_name = data['signerName']
        # Send a Twilio SMS if the envelope status changes to completed
        if envelope_status == 'Completed':
            print("Email :", signer_email, "Name :", signer_name)

            return JsonResponse({"message": "Twilio SMS sent."})

    return JsonResponse({"message": "Invalid request."})
