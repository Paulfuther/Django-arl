import json
import logging
import zipfile
import uuid
from io import BytesIO
from datetime import datetime, timedelta
import docusign_esign
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
    RecipientViewRequest,
)
import requests
from docusign_esign.client.api_exception import ApiException
from arl.bucket.helpers import upload_to_linode_object_storage
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
    # print("client id:", clientid, "impersonated_user_id :", impersonated_user_id)
    # print("private key in get access token :",private_key)
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
    print("envelop args in helper :", envelope_args)
    try:
        access_token = get_access_token().access_token
        print("access token :", access_token)
        
        template = envelope_args["template_id"]
        
        print("template :", template)
        if isinstance(template, str):  
            template = DocuSignTemplate.objects.filter(template_id=template).first()

        if not template:
            print("⚠️ No matching template found. Using default name.")
            template_name = "Default Template Name"
        else:
            template_name = template.template_name
        email_subject = f"{envelope_args['signer_name']} - {template_name}"
        print("template name: ", template_name)
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


def get_docusign_template_name_from_template(template_id):
    try:
        print("This is from the task get_docusign_template_name_from_template template id:", template_id)
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
        # print(temp_file)
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


def get_waiting_for_others_envelopes():
    try:
        access_token = get_access_token().access_token
        account_id = settings.DOCUSIGN_ACCOUNT_ID
        api_client = ApiClient()
        api_client.host = settings.DOCUSIGN_API_CLIENT_HOST
        api_client.set_default_header("Authorization", f"Bearer {access_token}")

        envelopes_api = EnvelopesApi(api_client)

        # Fetch envelopes created in the last 60 days
        from_date = (datetime.utcnow() - timedelta(days=60)).isoformat() + "Z"
        envelopes_list = envelopes_api.list_status_changes(
            account_id=account_id, from_date=from_date
        )

        outstanding_envelopes = []

        for envelope in envelopes_list.envelopes:
            if envelope.status in ["sent", "delivered"]:
                recipients = envelopes_api.list_recipients(
                    account_id, envelope.envelope_id
                )
                # Initialize a list to hold all signers for the current envelope
                outstanding_signers = []

                # Iterate over all signers and add them to the outstanding_signers list
                for signer in recipients.signers:
                    signer_info = {
                        "name": signer.name,
                        "email": signer.email,
                        "status": signer.status,
                        "recipient_id": signer.recipient_id,
                        "routing_order": signer.routing_order
                    }
                    outstanding_signers.append(signer_info)

                    # Print out the signer's information
                    print(f"Signer Name: {signer.name}")
                    print(f"Signer Email: {signer.email}")
                    print(f"Signer Status: {signer.status}")
                    print(f"Signer Recipient ID: {signer.recipient_id}")
                    print(f"Signer Routing Order: {signer.routing_order}")
                    print("-------------------")

                # Serialize the list of signers to JSON
                # serialized_signers = json.dumps(outstanding_signers)
                # print(f"Serialized Signers for envelope {envelope.envelope_id}: {serialized_signers}")

                # Retrieve the template name
                template_name = (
                    get_template_name_from_envelope(envelope.envelope_id)
                    or "Unknown Template"
                )
                if template_name != "Unknown Template":
                    print(f"Template name retrieved: {template_name}")
                else:
                    print("Template name not found.")

                # Append the details to the list of outstanding envelopes
                sent_date_time_as_date_time = parse_sent_date_time(envelope.sent_date_time)
                print(sent_date_time_as_date_time)
                outstanding_envelopes.append(
                    {
                        "template_name": template_name,
                        "status": envelope.status,
                        "sent_date_time": envelope.sent_date_time,
                        "signers": outstanding_signers,
                    }
                )

        return outstanding_envelopes

    except ApiException as e:
        print(f"Exception when calling EnvelopesApi->list_status_changes: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error occurred: {e}")
        return []


def get_template_name_from_envelope(envelope_id):
    access_token = get_access_token()
    access_token = access_token.access_token
    account_id = settings.DOCUSIGN_ACCOUNT_ID
    api_client = ApiClient()
    api_client.host = settings.DOCUSIGN_API_CLIENT_HOST
    api_client.set_default_header("Authorization", f"Bearer {access_token}")

    envelopes_api = EnvelopesApi(api_client)
    print(envelope_id)
    try:
        # Retrieve the list of templates used in the envelope
        template_data = envelopes_api.list_templates(account_id, envelope_id)
        # Ensure the response contains templates
        if hasattr(template_data, "templates") and template_data.templates:
            first_template = template_data.templates[0]
            template_name = (
                first_template.name if hasattr(first_template, "name") else None
            )
            if template_name:
                print(f"Template Name: {template_name}")
                return template_name
            else:
                print("Template Name not found.")
        else:
            print("No templates found in the data.")
            return None
    except ApiException as e:
        print(f"Exception when calling EnvelopesApi->list_templates: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error occurred: {e}")
        return None


def parse_sent_date_time(sent_date_time_str):
    if '.' in sent_date_time_str:
        sent_date_time_str = sent_date_time_str[:sent_date_time_str.index('Z')]  # Remove the trailing 'Z'
        date_part, fraction_part = sent_date_time_str.split('.')
        fraction_part = fraction_part[:6]  # Keep only up to 6 digits for microseconds
        sent_date_time_str = f"{date_part}.{fraction_part}Z"
    # Parse the datetime string
    return datetime.strptime(sent_date_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")


def get_docusign_edit_url(template_id):
    """
    Generates an editing URL for a DocuSign template.
    """
    base_url = settings.DOCUSIGN_BASE_PATH  # Example: "https://demo.docusign.net/restapi"
    account_id = settings.DOCUSIGN_ACCOUNT_ID
    access_token = get_access_token().access_token  # Ensure you have a function for authentication
    print(access_token)
    url = f"{base_url}/v2.1/accounts/{account_id}/templates/{template_id}/views/edit"
    print("url :", url)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # This return URL ensures they leave DocuSign after editing
    data = {
        "returnUrl": "https://www.1553690ontarioinc.com/",
        "suppressNavigation": "true"  # Restricts navigation inside DocuSign
    }

    response = requests.post(url, headers=headers, json=data)

    # DEBUG: Print full response
    print("Response Status:", response.status_code)
    print("Response Text:", response.text)
    if response.status_code == 201:
        return response.json().get("url")
    else:
        raise Exception(f"Failed to get edit URL: {response.json()}")


def get_embedded_envelope_url(user, template_id):
    """Generates an embedded URL for a DocuSign envelope based on a template."""
    access_token = get_access_token().access_token
    print("Access Token:", access_token)

    # ✅ Initialize DocuSign API Client
    api_client = ApiClient()
    api_client.host = settings.DOCUSIGN_API_CLIENT_HOST
    api_client.set_default_header("Authorization", "Bearer " + access_token)

    # ✅ Create Envelope Definition from Template
    envelope_definition = EnvelopeDefinition(
        template_id=template_id,
        status="sent"  # Set to 'created' if you need to edit before sending
    )

    # ✅ Create an Envelope
    envelopes_api = EnvelopesApi(api_client)
    envelope_summary = envelopes_api.create_envelope(
        settings.DOCUSIGN_ACCOUNT_ID,
        envelope_definition
    )

    # ✅ Generate an Embedded Signing URL
    recipient_view_request = RecipientViewRequest(
        return_url=f"{settings.SITE_URL}/dsign/templates/",  # Return after signing
        authentication_method="none",
        user_name=user.get_full_name(),
        email=user.email
    )

    response = envelopes_api.create_recipient_view(
        settings.DOCUSIGN_ACCOUNT_ID,
        envelope_summary.envelope_id,
        recipient_view_request
    )

    return response.url  # 🔹 Embed this in your Django template


def create_docusign_document(user, template_name="New Document"):
    """
    Creates a new blank DocuSign document and returns the template ID.
    """
    base_url = settings.DOCUSIGN_BASE_PATH
    account_id = settings.DOCUSIGN_ACCOUNT_ID
    access_token = get_access_token().access_token

    url = f"{base_url}/v2.1/accounts/{account_id}/templates"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Define a blank document
    data = {
        "name": template_name,
        "emailSubject": "Please sign this document",
        "recipients": {
        "signers": [
            {
                "roleName": "GSA",               # ✅ This is the role you’ll use later
                "recipientId": "1",
                "routingOrder": "1",
            }
        ]
    },
}

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 201:
        template_id = response.json().get("templateId")

        # ✅ Save the template in the database
        doc_template = DocuSignTemplate.objects.create(
            employer=user.employer,
            template_id=template_id,
            template_name=template_name,
        )

        print(f"✅ Template saved: {doc_template}")
        return template_id
    else:
        print(f"❌ ERROR: {response.status_code} - {response.text}")
        return None


def get_docusign_envelope(envelope_id, recipient_name=None, document_name=None):
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

        zip_file = envelopes_api.get_document(account_id, envelope_type, envelope_id)
        # print(temp_file)
        
        upload_to_dropbox(zip_file)
        logger.info(f"☁️ Uploaded ZIP file to Dropbox.")
        print("Uploaded zip file to dropox")
        # ✅ Extract ZIP contents
        zip_buffer = BytesIO(zip_file)
        folder_name = f"{uuid.uuid4().hex[:8]}"  # Unique folder name

        with zipfile.ZipFile(zip_buffer, "r") as zip_ref:
            extracted_files = zip_ref.namelist()
            logger.info(f"📂 Extracted {len(extracted_files)} files from ZIP.")
            print((f"📂 Extracted {len(extracted_files)} files from ZIP."))
            # ✅ Get employer for folder structure
            user = CustomUser.objects.filter(email__in=hr_users_emails).first()
            employer = user.employer if user else "UNKNOWN"
            print("Employer :", employer)
            if not employer:
                print("no employer")
                logger.error(f"❌ No employer found for user {user.email}")
                return HttpResponse("No employer found", status=400)

            employer_name = employer.name.replace(" ", "_")
            upload_folder_path = f"DOCUMENTS/{employer_name}/{folder_name}/"
            print("We are about to upload to linode")
            # ✅ Upload each extracted file to Linode
            for file_name in extracted_files:
                with zip_ref.open(file_name) as file:
                    file_data = file.read()
                    object_key = f"{upload_folder_path}{file_name}"
                    print(f"🔄 Preparing to upload {len(extracted_files)} files to Linode...")
                    logger.info(f"🔄 Preparing to upload {len(extracted_files)} files to Linode...")
                    upload_result = upload_to_linode_object_storage(BytesIO(file_data), object_key)
                    
                    if upload_result:
                        logger.info(f"✅ Uploaded {file_name} to Linode: {object_key}")
                        print(f"✅ Uploaded {file_name} to Linode: {object_key}")
                    else:
                        logger.error(f"❌ Failed to upload {file_name} to Linode.")
                        print(f"❌ Failed to upload {file_name} to Linode.")

        # Process the temp_file or perform actions like sending an email
        # Example: Sending an email with the retrieved document attached
        # email_subject = f"{document_name} completed for {recipient_name}"
        # email_body = f"Hello, this email contains a zip file that includes the {document_name} for {recipient_name} completed through docusign"

        # send_docusign_email_with_attachment(
        #     hr_users_emails, email_subject, email_body, zip_file
        # )

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

