from __future__ import absolute_import, unicode_literals

import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import Q
from docusign_esign import ApiClient, EnvelopesApi
from docusign_esign.client.api_exception import ApiException

from arl.celery import app
from arl.tasks import send_bulk_sms
from arl.user.models import CustomUser

from .helpers import (
    get_access_token,
    get_waiting_for_others_envelopes,
    parse_sent_date_time,
)

logger = logging.getLogger(__name__)


@app.task(name="list dsign envelopes")
def list_all_docusign_envelopes_task():
    access_token = get_access_token()
    access_token = access_token.access_token
    account_id = settings.DOCUSIGN_ACCOUNT_ID

    api_client = ApiClient()
    api_client.host = settings.DOCUSIGN_API_CLIENT_HOST
    api_client.set_default_header("Authorization", f"Bearer {access_token}")

    envelopes_api = EnvelopesApi(api_client)

    try:
        # List envelopes from the past month
        one_month_ago = (datetime.utcnow() - timedelta(days=60)).strftime("%Y-%m-%d")
        results = envelopes_api.list_status_changes(account_id, from_date=one_month_ago)

        # print("results : ", results)

        envelopes = []
        for envelope in results.envelopes:
            envelope_id = envelope.envelope_id
            email_results = envelopes_api.list_recipients(account_id, envelope_id)
            # print(email_results)
            emails = []
            for email in email_results.signers:
                emails.append({"email": email.email})

            envelopes.append(
                {
                    "envelope_id": envelope.envelope_id,
                    "status": envelope.status,
                    "email_subject": envelope.email_subject,
                    "sent_date_time": envelope.sent_date_time,
                    "email": emails,
                }
            )
        print("envelopes found")
        return envelopes

    except ApiException as e:
        print(f"Exception when calling EnvelopesApi->list_status_changes: {e}")
        return []


@app.task(name="sms for documents behind 48 hrs")
def check_outstanding_envelopes_task():
    outstanding_envelopes = get_waiting_for_others_envelopes()
    now = datetime.utcnow()
    behind_docs = []

    for envelope in outstanding_envelopes:
        sent_date_time = parse_sent_date_time(envelope["sent_date_time"])
        if now - sent_date_time >= timedelta(hours=48):
            # Get the name of the primary recipient (assuming the first signer is the main recipient)
            primary_recipient_name = (
                envelope["signers"][0].name
                if envelope["signers"]
                else "Unknown Recipient"
            )
            outstanding_signers = [
                signer.name
                for signer in envelope["signers"]
                if signer.status in ["sent", "delivered"]
            ]
            signer_list = (
                ", ".join(outstanding_signers)
                if outstanding_signers
                else "No outstanding signers"
            )
            # Add to the list of behind documents
            behind_docs.append(
                f"{envelope['template_name']} (Sent to: {primary_recipient_name}; Outstanding Signers: {signer_list})"
            )

    if behind_docs:
        document_list = "\n\n".join(behind_docs)
        message = f"The following documents are 48 hours behind:\n\n{document_list}"

        # Log the message that will be sent
        logger.info(f"Sending SMS: {message}")

        # Get all active users in the 'dsign_sms' group
        hr_users = CustomUser.objects.filter(
            Q(is_active=True) & Q(groups__name="dsign_sms")
        ).values_list("phone_number", flat=True)

        # Send the SMS message to all users in the group
        send_bulk_sms(hr_users, message)

        logger.info(f"Sent SMS for documents 48 hours behind to HR: {message}")
        return f"Sent SMS for documents 48 hours behind to HR: {document_list}"

    else:
        logger.info("No documents are 48 hours behind.")
        return "No documents are 48 hours behind."


@app.task(name="get outstanding docs")
def get_outstanding_docs():
    try:
        # Retrieve the outstanding envelopes
        envelopes = get_waiting_for_others_envelopes()

        # Serialize the envelopes and their signers
        serialized_envelopes = []
        for envelope in envelopes:
            # Assuming the primary recipient is the first signer
            primary_recipient_name = (
                envelope["signers"][0].name
                if envelope["signers"]
                else "Unknown Recipient"
            )
            serialized_signers = [
                {"name": signer.name, "email": signer.email, "status": signer.status}
                for signer in envelope["signers"]
            ]
            serialized_envelopes.append(
                {
                    "template_name": envelope["template_name"],
                    "status": envelope["status"],
                    "sent_date_time": envelope["sent_date_time"],
                    "primary_recipient": primary_recipient_name,
                    "signers": serialized_signers,
                }
            )

        # Log the number of outstanding envelopes found
        if serialized_envelopes:
            logger.info(f"Found {len(serialized_envelopes)} outstanding envelopes.")
        else:
            logger.info("No outstanding envelopes found.")

        return serialized_envelopes
    except Exception as e:
        # Log any errors that occur during the task execution
        logger.error(f"Error occurred in get_outstanding_docs task: {e}", exc_info=True)
        return []
