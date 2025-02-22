from __future__ import absolute_import, unicode_literals

import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import Q
from docusign_esign import ApiClient, EnvelopesApi
from docusign_esign.client.api_exception import ApiException

from arl.celery import app

from arl.dsign.models import DocuSignTemplate, ProcessedDocsignDocument
from arl.msg.tasks import send_bulk_sms
from arl.user.models import CustomUser

from .helpers import (create_docusign_envelope,
                      create_docusign_envelope_new_hire_quiz, get_access_token,
                      get_docusign_envelope, get_docusign_envelope_quiz,
                      get_docusign_template_name_from_template,
                      get_template_id, get_waiting_for_others_envelopes,
                      parse_sent_date_time)

logger = logging.getLogger(__name__)


def get_template_name(template_id):
    try:
        template = DocuSignTemplate.objects.get(template_id=template_id)
        return template.template_name
    except DocuSignTemplate.DoesNotExist:
        return None


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
        if now - sent_date_time >= timedelta(hours=336):
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
        if now - sent_date_time >= timedelta(hours=48):
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


@app.task(name="docusign_webhook")
def process_docusign_webhook(payload):
    envelope_id = payload.get("data", {}).get("envelopeId", "")
    if not envelope_id:
        logging.error("Envelope ID not found in the payload.")
        return
    # Assuming get_template_id is defined to extract
    # the template ID from the payload
    template_id = get_template_id(payload)
    if not template_id:
        print("No Template ID found.")
        return
    else:
        print(f"Template ID: {template_id}")
    # Use the envelopeId to get the template name
    template_name = get_docusign_template_name_from_template(template_id)
    print(f"template name is:  {template_name}")
    # Extract status and envelope summary from the payload
    status = payload.get("event", "")
    print(f"Status: {status}")
    envelope_summary = payload.get("data", {}).get("envelopeSummary", {})
    recipients = envelope_summary.get("recipients", {})
    signers = recipients.get("signers", [])
    recipient = signers[0]  # Assuming the first signer is
    recipient_email = recipient.get("email", "")
    if status == "envelope-sent":

        recipients = envelope_summary.get("recipients", {})
        signers = recipients.get("signers", [])
        if signers:
            print(f"Template Name second time: {template_name}")

            recipient = signers[0]  # Assuming the first signer is
            # the recipient
            recipient_email = recipient.get("email", "")

            # Optionally, fetch and print the recipient user's details
            # from CustomUser model
            try:
                user = CustomUser.objects.get(email=recipient_email)
                full_name = user.get_full_name()

                # print("fullname", full_name)
                # print(f"{template_name} sent to:
                # # {full_name} at {recipient_email}")
                hr_users = CustomUser.objects.filter(
                    Q(is_active=True) & Q(groups__name="dsign_sms")
                ).values_list("phone_number", flat=True)
                message_body = (
                    f"{template_name} sent to: {full_name} at "
                    f"{recipient_email}"
                )
                send_bulk_sms(hr_users, message_body)
                logger.info(
                    f"Sent SMS for 'sent' status to HR:{full_name}"
                    f" {message_body}"
                )
                return (
                    f"Sent SMS for 'sent' status to HR: {full_name}"
                    f" {template_name} {message_body}"
                )

            except CustomUser.DoesNotExist:
                logging.error(
                    f"User with email {recipient_email} "
                    f"not found in the database."
                )
            except Exception as e:
                logging.error(f"Error processing recipient data: {e}")

    elif status == "recipient-completed":
        # Check if the document is a Standard Release and exit if it is
        if "Standard Release" in template_name:
            print(
                f"Processed Standard Release for {recipient_email}"
                f", no further action."
            )
            return

        try:
            user = CustomUser.objects.get(email=recipient_email)
        except CustomUser.DoesNotExist:
            logging.error(
                f"User with email {recipient_email} not found in the database."
            )
            return  # Optionally handle the case where the user doesn't exist

        full_name = user.get_full_name()
        print(f"Template Name 3: {template_name}")

        if "New Hire File" in template_name:
            # Check if the user has already completed a new hire file
            user = CustomUser.objects.get(
                email=recipient_email
            )  # Assuming you have the user's email
            full_name = user.get_full_name()
            already_completed = ProcessedDocsignDocument.objects.filter(
                user=user, template_name="New Hire File"
            ).exists()
            if not already_completed:
                # Record this file to the db
                ProcessedDocsignDocument.objects.create(
                    user=user, envelope_id=template_id,
                    template_name=template_name
                )
                # Logic to send another file called New Hire Quiz
                # The quiz is not sent here.
                # it is sent through a post save signal to the documents
                # model

                get_docusign_envelope(envelope_id, full_name, template_name)

                print(f"New Hire Quiz needs to be sent to {user.email}")
            else:
                print("User has already completed a New Hire File.")

            # get the file for uplad

            hr_users = CustomUser.objects.filter(
                Q(is_active=True) & Q(groups__name="dsign_sms")
            ).values_list("phone_number", flat=True)

            message_body = (
                f"{template_name} completed by: {full_name} "
                f"at {recipient_email}"
            )
            send_bulk_sms(hr_users, message_body)
            logger.info(
                f"Sent SMS for 'completed' status to HR: {full_name} "
                f"{message_body}"
            )
            return (
                f"Sent SMS for 'completed' status to HR: "
                f"{full_name} {template_name} {message_body}"
            )
        else:
            # Record the completed non-new-hire file in
            # ProcessedDocsignDocument
            user = CustomUser.objects.get(email=recipient_email)
            print(full_name, recipient_email)
            ProcessedDocsignDocument.objects.create(
                user=user, envelope_id=template_id, template_name=template_name
            )
            print(f"Recorded completed file {template_name} for {user.email}")
            get_docusign_envelope_quiz(envelope_id, full_name, template_name)
            hr_users = CustomUser.objects.filter(
                Q(is_active=True) & Q(groups__name="dsign_sms")
            ).values_list("phone_number", flat=True)
            message_body = (
                f"{template_name} completed by: {full_name} "
                f"at {recipient_email}"
            )
            send_bulk_sms(hr_users, message_body)
            logger.info(
                f"Sent SMS for 'completed' status to HR:{full_name}"
                f" {message_body}"
            )
            return (
                f"Sent SMS for 'completed' status to HR: {full_name} "
                f"{template_name} {message_body}"
            )

    print("Done.")


@app.task(name="create_docusign_envelope")
def create_docusign_envelope_task(envelope_args):
    print("envelope args in task :", envelope_args)
    try:
        signer_name = envelope_args.get("signer_name")
        print(signer_name)
        create_docusign_envelope(envelope_args)

        logger.info(
            f"Docusign envelope New Hire File for {signer_name} "
            "created successfully"
        )
        return (
            f"Docusign envelope New Hire File for {signer_name} "
            "created successfully"
        )

    except Exception as e:
        logger.error(
            f"Error creating Docusign envelope New Hire File for "
            f"{signer_name}: {str(e)}"
        )
        return (
            f"Error creating Docusign envelope New Hire File for "
            f"{signer_name}: {str(e)}"
        )


@app.task(name="send_new_hire_quiz")
def send_new_hire_quiz(envelope_args):
    try:
        create_docusign_envelope_new_hire_quiz(envelope_args)
        signer_name = envelope_args.get("signer_name")
        logger.info(
            f"Docusign envelope New Hire Quiz for {signer_name} "
            f"created successfully"
        )

        return (
            f"Docusign envelope New Hire Quiz for {signer_name} "
            f"created successfully"
        )
    except Exception as e:
        logger.error(
            f"Error creating Docusign New Hire Quiz for {signer_name} "
            f"envelope: {str(e)}"
        )
        return (
            f"Error creating Docusign New Hire Quiz for {signer_name}"
            f"envelope: {str(e)}"
        )
