from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from docusign_esign import (
    ApiClient,
    EnvelopeDefinition,
    EnvelopesApi,
    RecipientEmailNotification,
    SignerAttachment,
    TemplateRole,
)
from docusign_esign.client.api_exception import ApiException
from arl.dbox.helpers import upload_to_dropbox
from arl.dsign.models import DocuSignTemplate
from arl.msg.helpers import create_single_email, send_docusign_email_with_attachment
from arl.user.models import CustomUser

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
    access_token = get_access_token().access_token
    # Construct the eventNotification
    # Note. We do not need this if we set the webhook notifications in the coe.
    # However, if we ever wanted to overide the notifications then we can
    # do so in the code.
    webhook_url = "https://www.arla0061.com/docusign-webhook"
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

    template = DocuSignTemplate.objects.get(template_id=envelope_args["template_id"])
    template_name = template.template_name if template else "Default Template Name"
    email_subject = f"{envelope_args['signer_name']} - {template_name}"
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


def get_docusign_envelope(envelope_id, recipient_name, document_name):
    try:
        hr_users_emails = CustomUser.objects.filter(
            Q(is_active=True) & Q(groups__name="dsign_email")
        ).values_list("email", flat=True)
        access_token = get_access_token()
        access_token = access_token.access_token
        api_client = ApiClient()
        api_client.host = settings.DOCUSIGN_API_CLIENT_HOST
        api_client.set_default_header("Authorization", "Bearer " + access_token)
        envelopes_api = EnvelopesApi(api_client)

        account_id = settings.DOCUSIGN_ACCOUNT_ID
        envelope_type = "archive"
        # envelope_id = "5d106d50-565e-4d70-85a4-0d1e29ff3abe"

        temp_file = envelopes_api.get_document(account_id, envelope_type, envelope_id)
        print(temp_file)
        upload_to_dropbox(temp_file) 
        # Process the temp_file or perform actions like sending an email
        # Example: Sending an email with the retrieved document attached
        email_subject = f"{document_name} completed for {recipient_name}"
        email_body = f"Hello, this email contains a zip file that includes the {document_name} for {recipient_name} completed through docusign"

        send_docusign_email_with_attachment(
            hr_users_emails, email_subject, email_body, temp_file
        )

        return HttpResponse("Process completed successfully.")

    except ApiException as e:
        # Handle specific API exceptions here
        error_message = f"DocuSign API Exception: {e}"
        print(error_message)
        return HttpResponse(f"An error occurred: {error_message}", status=500)

    except Exception as ex:
        # Handle other exceptions here
        error_message = f"An unexpected error occurred: {ex}"
        print(error_message)
        return HttpResponse(
            f"An unexpected error occurred: {error_message}", status=500
        )


def list_all_docusign_envelopes():
    access_token = get_access_token()
    access_token = access_token.access_token
    api_client = ApiClient()
    api_client.host = settings.DOCUSIGN_API_CLIENT_HOST
    api_client.set_default_header("Authorization", "Bearer " + access_token)
    envelopes_api = EnvelopesApi(api_client)
    print(envelopes_api)
    account_id = settings.DOCUSIGN_ACCOUNT_ID
    # envelope_type = "archive"
    # envelope_id = (
    #    "b8ba5457-5f2c-4199-ae64-afc66bd7f845/envelopes/394ab674-2c47-468e-92c5-"
    # )
    # temp_file = envelopes_api.get_search_folders(account_id, envelope_type,envelope_id)
    # temp_file = envelopes_api.get_search_folders(account_id)
    # print(temp_file)
    try:
        # List envelopes
        one_month_ago = (datetime.now() - timedelta(days=30)).isoformat()
        results = envelopes_api.list_status_changes(account_id, from_date=one_month_ago)

        # Print envelope information
        for envelope in results.envelopes:
            print(
                f"Envelope ID: {envelope.envelope_id}, Status: {envelope.status}, Sent: {envelope.sent_date_time}"
            )

    except ApiException as e:
        print(f"Exception when calling EnvelopesApi->list_status_changes: {e}")
    # Process the temp_file or perform actions like sending an email
    # Example: Sending an email with the retrieved document attached
    # email_subject = "Subject of the email"
    # email_body = "Body of the email"
    # recipient_email = "paul.futher@gmail.com"
    # create_single_email(recipient_email, email_subject, email_body, temp_file)
