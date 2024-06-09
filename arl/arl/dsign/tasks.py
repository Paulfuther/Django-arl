from __future__ import absolute_import, unicode_literals

from .helpers import get_access_token

from docusign_esign import (
    ApiClient,
    EnvelopesApi,
)
from docusign_esign.client.api_exception import ApiException
from django.conf import settings
from datetime import datetime, timedelta
from arl.celery import app


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
        one_month_ago = (datetime.utcnow() - timedelta(days=60)).strftime('%Y-%m-%d')
        results = envelopes_api.list_status_changes(account_id, from_date= one_month_ago)

        # print("results : ", results)

        envelopes = []
        for envelope in results.envelopes:
            envelope_id = envelope.envelope_id
            email_results = envelopes_api.list_recipients(account_id, envelope_id)
            # print(email_results)
            emails = []
            for email in email_results.signers:
                emails.append({
                    "email": email.email
                })
            
            envelopes.append({
                "envelope_id": envelope.envelope_id,
                "status": envelope.status,
                "email_subject": envelope.email_subject,
                "sent_date_time": envelope.sent_date_time,
                "email": emails,
            })
        print("envelopes found")
        return envelopes

    except ApiException as e:
        print(f"Exception when calling EnvelopesApi->list_status_changes: {e}")
        return []
