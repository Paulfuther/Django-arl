import os

from django.http import JsonResponse
from django.shortcuts import render
from docusign_esign import (ApiClient, EnvelopeDefinition, EnvelopesApi,
                            RecipientEmailNotification, SignerAttachment,
                            TemplateRole)

from .forms import NameEmailForm
from .helpers import get_access_token

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
            print(d_name, d_email)
            # ##clientid =DOCUSIGN_INTEGRATION_KEY
            # ##impersonated_user_id = DOCUSIGN_USER_ID
            access_token = get_access_token()
            access_token = access_token.access_token
            ds_template = os.environ.get('DOCUSIGN_TEMPLATE_ID')
            envelope_args = {
                "signer_email": d_email,
                "signer_name": d_name,
                "template_id": ds_template
            }

            args = {
                "base_path": "ca.docusign.net/restapi",
                "ds_access_token": access_token,
                "account_id": os.environ.get('DOCUSIGN_ACCOUNT_ID'),
                "envelope_args": envelope_args
            }

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
            api_client.host = 'https://ca.docusign.net/restapi'  # Update with the correct base path
            api_client.set_default_header("Authorization", "Bearer " + access_token)  # Replace with your access token
            envelope_api = EnvelopesApi(api_client)
            try:
                results = envelope_api.create_envelope(os.environ.get('DOCUSIGN_ACCOUNT_ID'),
                                                    envelope_definition=envelope_definition)
                envelope_id = results.envelope_id
                return JsonResponse({'envelope_id': envelope_id})
            except Exception as e:
                return JsonResponse({'error': str(e)}), 500
    else:
        form = NameEmailForm()
        return render(request, 'dsign/name_email_form.html', {'form': form})