import os

from django.http import JsonResponse
from docusign_esign import ApiClient, EnvelopesApi, EnvelopeDefinition, TemplateRole, SignHere
from .helpers import get_access_token


# Create your views here.

def create_envelope(request):
    # ##clientid =DOCUSIGN_INTEGRATION_KEY
    # ##impersonated_user_id = DOCUSIGN_USER_ID
    access_token = get_access_token()
    access_token = access_token.access_token

    envelope_args = {
        "signer_email": "paul.futher@gmail.com",
        "signer_name": "paul futher",
        "template_id": "cba592aa-9eaf-479e-9826-92da63b8f850"
    }

    args = {
        "base_path": "demo.docusign.net/restapi",
        "ds_access_token": access_token,
        "account_id": os.environ.get('DOCUSIGN_ACCOUNT_ID'),
        "envelope_args": envelope_args
    }

    # Create the envelope definition
    envelope_definition = EnvelopeDefinition(
        status="sent",  # requests that the envelope be created and sent.
        template_id=envelope_args['template_id'],
        auto_navigation=False
    )

    # Create the signer role
    signer = TemplateRole(
        email=envelope_args['signer_email'],
        name=envelope_args['signer_name'],
        role_name='signer'
    )

    # Create a SignHere tab with anchor string configuration
    sign_here_tab = SignHere(
        anchor_string="Please Sign Here",
        anchor_x_offset="0",
        anchor_y_offset="-0.5",
        anchor_units="inches",
        anchor_ignore_if_not_present="false",
        
    )

    # Add the SignHere tab to the signer role
    signer.tabs = {
        "signHereTabs": [sign_here_tab]
    }

    # Add the TemplateRole objects to the envelope object
    envelope_definition.template_roles = [signer]

    api_client = ApiClient()
    print("1", api_client)
    api_client.host = "https://demo.docusign.net/restapi"  # Update with the correct base path
    api_client.set_default_header("Authorization", "Bearer " + access_token)  # Replace with your access token
    envelope_api = EnvelopesApi(api_client)

    try:
        results = envelope_api.create_envelope(os.environ.get('DOCUSIGN_ACCOUNT_ID'),
                                               envelope_definition=envelope_definition)
        envelope_id = results.envelope_id
        return JsonResponse({'envelope_id': envelope_id})
    except Exception as e:
        return JsonResponse({'error': str(e)}), 500
