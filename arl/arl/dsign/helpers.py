import json
import logging
from datetime import datetime, timedelta

import requests
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
    TemplatesApi,
)
from docusign_esign.client.api_exception import ApiException

from arl.dbox.helpers import upload_to_dropbox, upload_to_dropbox_quiz
from arl.dsign.models import DocuSignTemplate
from arl.msg.helpers import send_docusign_email_with_attachment
from arl.user.models import CustomUser

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

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
    try:
        access_token = get_access_token().access_token

        template = DocuSignTemplate.objects.get(
            template_id=envelope_args["template_id"]
        )
        template_name = template.template_name if template else "Default Template Name"
        email_subject = f"{envelope_args['signer_name']} - {template_name}"

        # Create the envelope definition
        envelope_definition = EnvelopeDefinition(
            status="sent",  # requests that the envelope be created and sent.
            template_id=envelope_args["template_id"],
            auto_navigation=False,
        )

        # Create the signer role
        signer = TemplateRole(
            email=envelope_args["signer_email"],
            name=envelope_args["signer_name"],
            role_name="GSA",
            email_notification=RecipientEmailNotification(email_subject=email_subject),
        )
        print(
            "Here are the details:",
            envelope_args["signer_email"],
            envelope_args["signer_name"],
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
        api_client.set_default_header("Authorization", "Bearer " + access_token)
        envelope_api = EnvelopesApi(api_client)

        results = envelope_api.create_envelope(
            settings.DOCUSIGN_ACCOUNT_ID, envelope_definition=envelope_definition
        )
        envelope_id = results.envelope_id
        logger.info(
            f"Docusign envelope {envelope_id} created successfully for {envelope_args['signer_name']}"
        )
        return f"Docusign envelope {envelope_id} created successfully for {envelope_args['signer_name']}"
    except Exception as e:
        logger.error(f"Error creating Docusign envelope: {str(e)}")
        return f"Error creating Docusign envelope: {str(e)}"


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


def get_docusign_template_name_from_template(template_id):
    try:
        print("template id:", template_id)
        # Authenticate with DocuSign API (use your own authentication method)
        access_token = get_access_token()  # Replace with your authentication method
        access_token = access_token.access_token
        api_client = ApiClient()
        api_client.host = settings.DOCUSIGN_API_CLIENT_HOST
        api_client.set_default_header("Authorization", "Bearer " + access_token)
        account_id = settings.DOCUSIGN_ACCOUNT_ID
        # Create the EnvelopesApi and TemplatesApi objects
        # Create the TemplatesApi object
        # Initialize the Templates API
        templates_api = TemplatesApi(api_client)

        # Get the template details using the template ID
        template = templates_api.get(account_id, template_id)
        template_name = template.name if template else None

        if template_name:
            print(f"Template name in hlerp  task: {template_name}")
            return template_name
        else:
            print("Template name not found for the given template ID.")
            return None

    except Exception as e:
        print(f"Error retrieving DocuSign template name: {str(e)}")
        return None


def fetch_envelope_details(envelope_id):
    # Example variables - replace with your actual data
    base_url = "https://demo.docusign.net/restapi"
    account_id = settings.DOCUSIGN_ACCOUNT_ID
    access_token = get_access_token()  # Replace with your authentication method
    access_token = access_token.access_token
    headers = {"Authorization": f"Bearer {access_token}"}

    # Construct the API endpoint URL
    url = f"{base_url}/v2.1/accounts/{account_id}/envelopes/{envelope_id}"

    # Make the GET request
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        # Assuming the request was successful, parse the response
        envelope_details = response.json()
        return envelope_details
    else:
        # Handle errors or unsuccessful requests
        print(f"Failed to fetch envelope details. Status code: {response.status_code}")
        return None


def get_template_id(payload):
    # Setup for DocuSign API Client
    api_client = ApiClient()
    api_client.host = settings.DOCUSIGN_API_CLIENT_HOST
    access_token = get_access_token()
    access_token = access_token.access_token
    api_client.set_default_header("Authorization", f"Bearer {access_token}")

    try:
        # Extract envelope ID from payload
        if isinstance(payload, str):
            payload = json.loads(payload)
        envelope_id = payload.get("data", {}).get("envelopeId", "")
        if not envelope_id:
            logging.error("Envelope ID could not be found in the payload.")
            return None

        # Fetch templates associated with the envelope
        envelopes_api = EnvelopesApi(api_client)
        account_id = (
            settings.DOCUSIGN_ACCOUNT_ID
        )  # Replace with your DocuSign account ID
        templates_response = envelopes_api.list_templates(
            account_id=account_id, envelope_id=envelope_id
        )

        # Process the templates response
        if (
            templates_response
            and hasattr(templates_response, "templates")
            and templates_response.templates
        ):
            first_template = templates_response.templates[0]
            template_id = (
                first_template.template_id
                if hasattr(first_template, "template_id")
                else None
            )
            if template_id:
                logging.info(
                    f"Template ID for Envelope ID {envelope_id}: {template_id}"
                )
                return template_id
            else:
                logging.error(
                    f"No template details found for the Envelope ID {envelope_id}."
                )
                return None
    except ApiException as e:
        logging.error(f"DocuSign API exception: {e}")
    except Exception as e:
        logging.error(f"Error processing webhook payload: {e}")
    return None


def create_docusign_envelope_new_hire_quiz(envelope_args):
    access_token = get_access_token().access_token
    # Construct the eventNotification
    # Note. We do not need this if we set the webhook notifications in the coe.
    # However, if we ever wanted to overide the notifications then we can
    # do so in the code.

    template = DocuSignTemplate.objects.get(template_id=envelope_args["template_id"])
    template_name = template.template_name if template else "Default Template Name"
    email_subject = (
        f"{envelope_args['signer_name']} please complete this file - {template_name}"
    )
    # Construct the email subject for the second signer
    email_subject2 = f"{template_name} for {envelope_args['signer_name']} for review by {envelope_args['manager_name']}"
    # Create the envelope definition
    envelope_definition = EnvelopeDefinition(
        status="sent",  # requests that the envelope be created and sent.
        template_id=envelope_args["template_id"],
        auto_navigation=False,
    )

    # Create the signer role
    signer = TemplateRole(
        email=envelope_args["signer_email"],
        name=envelope_args["signer_name"],
        role_name="GSA",
        email_notification=RecipientEmailNotification(email_subject=email_subject),
        recipient_id="1",
        routing_order="1",
    )

    signer2 = TemplateRole(
        email=envelope_args["manager_email"],
        name=envelope_args["manager_name"],
        role_name="Manager",  # This should also match the role defined in your DocuSign template
        email_notification=RecipientEmailNotification(email_subject=email_subject2),
        recipient_id="2",
        routing_order="2",
    )

    # Add the TemplateRole objects to the envelope object
    envelope_definition.template_roles = [signer, signer2]
    api_client = ApiClient()
    api_client.host = settings.DOCUSIGN_API_CLIENT_HOST
    api_client.set_default_header("Authorization", "Bearer " + access_token)
    envelope_api = EnvelopesApi(api_client)
    try:
        results = envelope_api.create_envelope(
            settings.DOCUSIGN_ACCOUNT_ID, envelope_definition=envelope_definition
        )
        envelope_id = results.envelope_id
        return JsonResponse({"envelope_id": envelope_id})
    except Exception as e:
        print("error")
        return JsonResponse({"error": str(e)}), 500


def get_waiting_for_others_envelopes():
    access_token = get_access_token()
    access_token = access_token.access_token
    account_id = settings.DOCUSIGN_ACCOUNT_ID
    api_client = ApiClient()
    api_client.host = settings.DOCUSIGN_API_CLIENT_HOST
    api_client.set_default_header("Authorization", f"Bearer {access_token}")

    envelopes_api = EnvelopesApi(api_client)
    try:
        # Fetch envelopes without specifying the status
        from_date = (
            datetime.utcnow() - timedelta(days=60)
        ).isoformat() + "Z"  # Adjust the date range as needed
        envelopes_list = envelopes_api.list_status_changes(
            account_id=account_id,
            from_date=from_date,
        )

        outstanding_envelopes = []

        for envelope in envelopes_list.envelopes:
            if envelope.status in ["sent", "delivered"]:
                recipients = envelopes_api.list_recipients(
                    account_id, envelope.envelope_id
                )
                outstanding_signers = [
                    signer
                    for signer in recipients.signers
                    if signer.status in ["sent", "delivered"]
                ]

                # Fetch the template ID from the custom fields
                custom_fields = envelopes_api.list_custom_fields(
                    account_id, envelope.envelope_id
                )
                template_id = None
                for text_custom_field in custom_fields.text_custom_fields:
                    if text_custom_field.name == "TemplateID":
                        template_id = text_custom_field.value
                        print(template_id)
                        break

                # Fetch the template name using the helper function
                template_name = (
                    get_docusign_template_name_from_template(template_id)
                    if template_id
                    else "Unknown Template"
                )
                outstanding_envelopes.append(
                    {
                        "template_name": template_name,
                        "status": envelope.status,
                        "sent_date_time": envelope.sent_date_time,
                        "signers": outstanding_signers,
                    }
                )
                print("template name:", template_name)
        return outstanding_envelopes
    except ApiException as e:
        print(f"Exception when calling EnvelopesApi->list_status_changes: {e}")
        return []


def get_docusign_envelope_quiz(envelope_id, recipient_name, document_name):
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
        upload_to_dropbox_quiz(temp_file)
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
