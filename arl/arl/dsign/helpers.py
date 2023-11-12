from django.conf import settings
from django.http import JsonResponse
from docusign_esign import (
    ApiClient,
    EnvelopeDefinition,
    EnvelopesApi,
    RecipientEmailNotification,
    SignerAttachment,
    TemplateRole,
)

SCOPES = ["signature impersonation"]


def get_jwt_token(private_key, scopes, auth_server, client_id, impersonated_user_id):
    """Get the jwt token"""
    api_client = ApiClient()
    api_client.set_base_path(auth_server)
    response = api_client.request_jwt_user_token(
        client_id=client_id,
        user_id=impersonated_user_id,
        oauth_host_name=auth_server,
        private_key_bytes=private_key,
        expires_in=4000,
        scopes=scopes,
    )
    return response


def create_api_client(base_path, access_token):
    """Create api client and construct API headers"""
    api_client = ApiClient()
    api_client.host = base_path
    api_client.set_default_header(
        header_name="Authorization", header_value=f"Bearer {access_token}"
    )

    return api_client


def get_access_token():
    api_client = ApiClient()
    api_client.host = settings.DOCUSIGN_API_CLIENT_HOST
    # Configure your API credentials
    # print(api_client.host)
    clientid = settings.DOCUSIGN_INTEGRATION_KEY
    impersonated_user_id = settings.DOCUSIGN_USER_ID
    in_file = open(settings.DOCUSIGN_PRIVATE_KEY, "rb")
    private_key = in_file.read()
    # print(private_key)
    in_file.close()
    # print(settings.DOCUSIGN_OAUTH_HOST_NAME)
    access_token = api_client.request_jwt_user_token(
        client_id=clientid,
        user_id=impersonated_user_id,
        oauth_host_name=settings.DOCUSIGN_OAUTH_HOST_NAME,
        private_key_bytes=private_key,
        expires_in=3600,
        scopes=SCOPES,
    )
    # print(access_token)
    return access_token


def create_docusign_envelope(envelope_args):
    access_token = get_access_token()
    access_token = access_token.access_token
    args = {
        "base_path": settings.DOCUSIGN_BASE_PATH,
        "ds_access_token": access_token,
        "account_id": settings.DOCUSIGN_ACCOUNT_ID,
        "envelope_args": envelope_args,
    }
    # print(args)

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
            {"envelopeEventStatusCode": "voided"},
        ],
        "recipientEvents": [
            {"recipientEventStatusCode": "Sent"},
            {"recipientEventStatusCode": "Delivered"},
            {"recipientEventStatusCode": "Completed"},
            {"recipientEventStatusCode": "Declined"},
            {"recipientEventStatusCode": "AuthenticationFailed"},
            {"recipientEventStatusCode": "AutoResponded"},
        ],
    }

    email_subject = f"{envelope_args['signer_name']} - {'New Hire File'}"
    # print(email_subject)
    # Create the envelope definition
    envelope_definition = EnvelopeDefinition(
        status="sent",  # requests that the envelope be created and sent.
        template_id=envelope_args["template_id"],
        eventNotification=event_notification,
        auto_navigation=False,
    )

    # Create the signer role
    signer = TemplateRole(
        email=envelope_args["signer_email"],
        name=envelope_args["signer_name"],
        role_name="GSA",
        email_notification=RecipientEmailNotification(email_subject=email_subject),
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
        optional="false",
    )

    attachment_tab3 = SignerAttachment(
        anchor_string="/void ch/",
        anchor_x_offset="0",
        anchor_y_offset="0",
        anchor_units="inches",
        tab_label="ID_Image3",
        optional="false",
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
        results = envelope_api.create_envelope(
            settings.DOCUSIGN_ACCOUNT_ID, envelope_definition=envelope_definition
        )
        envelope_id = results.envelope_id
        return JsonResponse({"envelope_id": envelope_id})
    except Exception as e:
        print("error")
        return JsonResponse({"error": str(e)}), 500
    
