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
        one_month_ago = ((datetime.utcnow() -
                          timedelta(days=60)).strftime("%Y-%m-%d"))
        results = (
            envelopes_api.list_status_changes(account_id,
                                              from_date=one_month_ago)
        )

        # print("results : ", results)

        envelopes = []
        for envelope in results.envelopes:
            envelope_id = envelope.envelope_id
            email_results = envelopes_api.list_recipients(account_id,
                                                          envelope_id)
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
    managers_to_notify = set()

    for envelope in outstanding_envelopes:
        sent_date_time = parse_sent_date_time(envelope["sent_date_time"])
        if now - sent_date_time >= timedelta(hours=48):
            # Check if there are any signers
            if envelope["signers"]:
                # Assuming the primary recipient is the first signer
                primary_recipient_name = envelope["signers"][0]["name"]
                # Retrieve the store manager for the primary recipient
                try:
                    primary_recipient_email = envelope["signers"][0]["email"]
                    user = (
                        CustomUser.objects.get
                        (email=primary_recipient_email)
                    )
                    store_manager = (
                        user.store.manager if user.store and
                        user.store.manager else None
                    )
                    if store_manager:
                        # Add the manager's phone number to
                        # the notification list
                        managers_to_notify.add(store_manager.phone_number)
                    else:
                        store_manager = "No Manager Assigned"
                except CustomUser.DoesNotExist:
                    store_manager = "Manager Not Found"

                # Prepare a detailed list of outstanding
                # signers with their role, store, and address
                outstanding_signers_info = []
                for signer in envelope["signers"]:
                    if signer["status"] in ["sent", "delivered"]:
                        # Query the CustomUser model for
                        # store and role based on the signer's email
                        try:
                            user = (
                                CustomUser.objects.get(email=signer["email"])
                            )
                            store_name = (
                                user.store.number if user.store
                                else "No Store Assigned"
                            )
                            store_address = (
                                user.store.address if user.store
                                else "No Address Available"
                            )
                            role = (
                                user.groups.first().name if
                                user.groups.exists()
                                else "No Role Assigned"
                            )
                        except CustomUser.DoesNotExist:
                            store_name = "User Not Found"
                            store_address = "Address Not Found"
                            role = "Role Not Found"

                        signer_info = (
                            f"Name: {signer['name']}\n"
                            f"Email: {signer['email']}\n"
                            f"Role: {role}\n"
                            f"Store: {store_name}\n"
                            f"Address: {store_address}\n"
                        )
                        outstanding_signers_info.append(signer_info)

                signer_list = (
                    "\n".join(outstanding_signers_info)
                    if outstanding_signers_info
                    else "No outstanding signers"
                )
            else:
                primary_recipient_name = "Unknown Recipient"
                store_manager = "Manager Not Found"
                signer_list = "No signers available"

            # Add to the list of behind documents
            # with detailed signer information
            behind_docs.append(
                f"Document: {envelope['template_name']}\n"
                f"Sent to: {primary_recipient_name}\n"
                f"Manager: {store_manager}\n"
                f"Outstanding Signers:\n{signer_list}"
            )

    if behind_docs:
        document_list = "\n\n".join(behind_docs)
        message = (
            f"The following documents are 48 hours behind:\n\n"
            f"{document_list}"
        )

        # Log the message that will be sent
        logger.info(f"Sending SMS: {message}")

        # Get all active users in the 'dsign_sms' group
        hr_users = CustomUser.objects.filter(
            Q(is_active=True) & Q(groups__name="dsign_sms")
        ).values_list("phone_number", flat=True)
        # Combine HR users and managers into one recipient list
        recipients = list(hr_users) + list(managers_to_notify)
        # Send the SMS message to all users in the group
        # print("recipients:", recipients)
        send_bulk_sms(recipients, message)

        logger.info(f"Sent SMS for documents 48 hours behind to HR: {message}")
        return f"Sent SMS for documents 48 hours behind to HR: {document_list}"

    else:
        logger.info("No documents are 48 hours behind.")
        return "No documents are 48 hours behind."


@app.task(name="weekly sms for documents behind 48 hrs")
def check_outstanding_envelopes_weekly_sms_task():
    outstanding_envelopes = get_waiting_for_others_envelopes()
    now = datetime.utcnow()
    behind_docs = []

    for envelope in outstanding_envelopes:
        sent_date_time = parse_sent_date_time(envelope["sent_date_time"])
        if now - sent_date_time >= timedelta(hours=0):
            # Check if there are any signers
            if envelope["signers"]:
                # Assuming the primary recipient is the first signer
                primary_recipient_name = envelope["signers"][0]["name"]
                # Retrieve the store manager for the primary recipient
                try:
                    primary_recipient_email = envelope["signers"][0]["email"]
                    user = CustomUser.objects.get(
                        email=primary_recipient_email)
                    store_manager = (
                        user.store.manager
                        if user.store and user.store.manager else
                        "No Manager Assigned"
                    )
                except CustomUser.DoesNotExist:
                    store_manager = "Manager Not Found"

                # Prepare a detailed list of outstanding
                # signers with their role, store, and address
                outstanding_signers_info = []
                for signer in envelope["signers"]:
                    if signer["status"] in ["sent", "delivered"]:
                        # Query the CustomUser model for store
                        # and role based on the signer's email
                        try:
                            user = (
                                CustomUser.objects.get(email=signer["email"])
                            )
                            store_name = (
                                user.store.number
                                if user.store else "No Store Assigned"
                            )
                            store_address = (
                                user.store.address if
                                user.store else "No Address Available"
                            )
                            role = (
                                user.groups.first().name if
                                user.groups.exists() else
                                "No Role Assigned"
                            )

                        except CustomUser.DoesNotExist:
                            store_name = "User Not Found"
                            store_address = "Address Not Found"
                            role = "Role Not Found"

                        signer_info = (
                            f"Name: {signer['name']}\n"
                            f"Email: {signer['email']}\n"
                            f"Role: {role}\n"
                            f"Store: {store_name}\n"
                            f"Address: {store_address}\n"
                        )
                        outstanding_signers_info.append(signer_info)

                signer_list = (
                    "\n".join(outstanding_signers_info)
                    if outstanding_signers_info
                    else "No outstanding signers"
                )
            else:
                primary_recipient_name = "Unknown Recipient"
                store_manager = "Manager Not Found"
                signer_list = "No signers available"

            # Add to the list of behind documents with detailed
            # signer information
            behind_docs.append(
                f"Document: {envelope['template_name']}\n"
                f"Sent to: {primary_recipient_name}\n"
                f"Manager: {store_manager}\n"
                f"Outstanding Signers:\n{signer_list}"
            )

    if behind_docs:
        document_list = "\n\n".join(behind_docs)
        message = (
            f"The following documents are 48 hours behind: \n\n"
            f"{document_list}"
        )

        # Log the message that will be sent
        logger.info(f"Sending SMS: {message}")

        # Get all active users in the 'dsign_sms' group
        hr_users = CustomUser.objects.filter(
            Q(is_active=True) & Q(groups__name="weekly_dsign_sms")
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
        serialized_envelopes = []

        for envelope in envelopes:
            # Check if there are signers
            if envelope["signers"]:
                primary_recipient_name = envelope["signers"][0]["name"]
                serialized_signers = []

                for signer in envelope["signers"]:
                    # Skip signers that have already completed signing
                    if signer["status"].lower() == "completed":
                        continue
                    # Query the CustomUser model for store and role
                    try:
                        user = CustomUser.objects.get(email=signer["email"])
                        store = (
                            user.store.number if user.store else
                            "No Store Assigned"
                        )
                        store_address = (
                            user.store.address if user.store
                            else "No Address Available"
                        )
                        role = (
                            user.groups.first().name if user.groups.exists()
                            else "No Role Assigned"
                        )
                        print(store, role)
                    except CustomUser.DoesNotExist:
                        store = "User Not Found"
                        store_address = "Address Not Found"
                        role = "Role Not Found"

                    # Add signer information along with store and role
                    serialized_signers.append(
                        {
                            "name": signer["name"],
                            "email": signer["email"],
                            "status": signer["status"],
                            "store": store,
                            "address": store_address,
                            "role": role,
                        }
                    )

            else:
                primary_recipient_name = "Unknown Recipient"
                serialized_signers = []

            # Append the serialized envelope data
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
            logger.info(
                f"Found {len(serialized_envelopes)}"
                f" outstanding envelopes.")
        else:
            logger.info("No outstanding envelopes found.")

        return serialized_envelopes

    except Exception as e:
        # Log any errors that occur during the task execution
        logger.error(
            f"Error occurred in get_outstanding_docs task: {e}"
            f", exc_info=True")
        return []
