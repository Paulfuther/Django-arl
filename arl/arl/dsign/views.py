import json
import logging
import uuid

from celery.result import AsyncResult
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from docusign_esign import ApiClient, ApiException, TemplatesApi

from arl.bucket.helpers import upload_to_linode_object_storage
from arl.dsign.helpers import (
    create_docusign_document,
    get_access_token,
    get_docusign_envelope,
    get_docusign_template_name_from_template,
    create_envelope_for_in_app_signing,
    get_recipient_view_url,
    get_template_signature_validation
)
from arl.dsign.tasks import (get_outstanding_docs,
                             list_all_docusign_envelopes_task)

from .forms import MultiSignedDocUploadForm, NameEmailForm
from .helpers import get_docusign_edit_url
from .models import DocuSignTemplate, SignedDocumentFile
from .tasks import (
    create_docusign_envelope_task,
    process_docusign_webhook,
    validate_template_signature_tabs_task,
)

logger = logging.getLogger(__name__)


def is_member_of_msg_group(user):
    is_member = user.groups.filter(name="docusign").exists()
    if is_member:
        logger.info(f"{user} is a member of 'docusign' group.")
    else:
        logger.info(f"{user} is not a member of 'docusign' group.")
    return is_member


class CreateEnvelopeView(UserPassesTestMixin, View):
    def test_func(self):
        return is_member_of_msg_group(self.request.user)

    def get(self, request):
        form = NameEmailForm(user=request.user)
        return render(request, "dsign/name_email_form.html", {"form": form})

    def post(self, request):
        form = NameEmailForm(request.POST, user=request.user)
        if form.is_valid():
            recipient = form.cleaned_data["recipient"]
            ds_template = form.cleaned_data["template_id"]
            template = form.cleaned_data["template_name"]
            template_name = template.template_name if template else "Unknown Template"

            envelope_args = {
                "signer_email": recipient.email,
                "signer_name": recipient.get_full_name(),
                "template_id": ds_template,
            }

            print("Here are the args:", envelope_args)

            create_docusign_envelope_task.delay(envelope_args)

            messages.success(
                request,
                f"Thank you. The document '{template_name}' has been sent to {recipient.get_full_name()}.",
            )
            return redirect("home")


@csrf_exempt  # In production, use proper CSRF protection.
def docusign_webhook(request):
    if request.method == "POST":
        try:
            payload = json.loads(request.body.decode("utf-8"))
            process_docusign_webhook.delay(payload)
            return JsonResponse({"message": "Webhook processed successfully"})

        except json.JSONDecodeError:
            logger.error("Invalid JSON payload")
            return JsonResponse({"error": "Invalid JSON payload"}, status=400)

        except Exception as e:
            logger.error(f"Error processing DocuSign webhook: {str(e)}")
            return JsonResponse(
                {"error": f"Error processing DocuSign webhook: {str(e)}"}, status=500
            )

    else:
        return JsonResponse({"error": "Only POST requests are allowed"}, status=405)


def retrieve_docusign_envelope(request):
    try:
        get_docusign_envelope()
        messages.success(request, "Docusign Document Has Been Emailed.")
    except Exception as e:
        messages.error(request, f"Process failed: {str(e)}")

    return redirect("home")


def list_docusign_envelope(request):
    try:
        task_id = request.session.get("list_envelopes_task_id")
        if not task_id:
            # Start the task and save the task ID in the session
            task = list_all_docusign_envelopes_task.delay()
            request.session["list_envelopes_task_id"] = task.id
            logger.info(
                "Started list_all_docusign_envelopes_task with task_id: %s", task.id
            )
            return render(request, "dsign/loading.html")  # Render a loading template

        task_result = AsyncResult(task_id)
        logger.info("Task state: %s", task_result.state)
        print("Task sate: ", task_result.state)
        if task_result.state == "SUCCESS":
            # Task completed successfully
            envelopes = task_result.result
            # Clear the task ID from the session
            del request.session["list_envelopes_task_id"]
            logger.info("Task completed successfully with result: %s", envelopes)
            return render(
                request, "dsign/list_envelopes.html", {"envelopes": envelopes}
            )
        elif task_result.state == "FAILURE":
            # Task failed
            error_message = str(task_result.result)
            # Clear the task ID from the session
            del request.session["list_envelopes_task_id"]
            logger.error("Task failed with error: %s", error_message)
            return render(request, "dsign/error.html", {"error": error_message})
        else:
            # Task is still processing
            logger.info("Task is still processing")
            return render(request, "dsign/loading.html")  # Render a loading template
    except Exception as e:
        logger.error("An error occurred in list_docusign_envelope: %s", str(e))
        return render(request, "dsign/error.html", {"error": str(e)})


def get_docusign_template(request):
    envelope_id = (
        "db908cae-87ac-4c37-aa67-d5a971ee7da7"  # Replace with your envelope_id
    )
    print(envelope_id)
    template_name = get_docusign_template_name_from_template(envelope_id)

    if template_name:
        return JsonResponse({"template_name": template_name})
    else:
        return JsonResponse(
            {"error": "Template not found in the envelope."}, status=404
        )


@login_required
def waiting_for_others_view(request):
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        # Handle the AJAX request to fetch the outstanding documents
        result = get_outstanding_docs.delay()
        envelopes = result.get(timeout=10)  # Adjust the timeout as needed
        return JsonResponse({"outstanding_envelopes": envelopes})
    # Render the template for the initial page load
    return render(request, "dsign/waiting_for_others.html")


@login_required
def create_new_document_page(request):
    """Handles creating a new DocuSign document and saving it in Django."""

    if request.method == "POST":
        template_name = request.POST.get("template_name", "New Document")
        print("Template Name :", template_name)
        template_id = create_docusign_document(
            user=request.user, template_name=template_name
        )

        if template_id:
            messages.success(
                request, f"Document '{template_name}' created successfully!"
            )
            # ✅ Get the edit URL for the new template
            edit_url = get_docusign_edit_url(template_id)

            if edit_url:
                return redirect(edit_url)  # ✅ Immediately open the DocuSign editor
            else:
                messages.error(
                    request, "Could not retrieve the edit URL. Please try manually."
                )
        else:
            messages.error(request, "Failed to create a new document.")

        return redirect("hr_dashboard")  # Redirect to HR dashboard

    return render(request, "dsign/create_document.html")


@login_required
def edit_document_page(request, template_id):
    """Shows helper info, then lets user continue to DocuSign editor."""
    edit_url = get_docusign_edit_url(template_id)
    template = DocuSignTemplate.objects.filter(template_id=template_id).first()

    # ✅ Run the helper directly (sync)
    validation_result = get_template_signature_validation(template_id)
    has_sign_here_tab = validation_result.get('has_sign_here', False)

    return render(
        request,
        "dsign/dsign_redirect.html",
        {
            "edit_url": edit_url,
            "template": template,
            "has_sign_here_tab": has_sign_here_tab,
        },
    )


def check_docusign_template_ready(template_id):
    access_token = get_access_token().access_token
    base_path = settings.DOCUSIGN_BASE_PATH
    account_id = settings.DOCUSIGN_ACCOUNT_ID
    api_client = ApiClient()
    api_client.host = base_path
    api_client.set_default_header("Authorization", f"Bearer {access_token}")

    templates_api = TemplatesApi(api_client)

    try:
        template = templates_api.get(account_id, template_id)

        # ✅ Basic checks
        has_docs = bool(template.documents)
        has_subject = bool(template.email_subject and template.email_subject.strip())
        has_signers = bool(template.recipients and template.recipients.signers)

        if not (has_docs and has_subject and has_signers):
            print("❌ Missing docs, subject, or signers.")
            return False

        gsa_signed = False

        for signer in template.recipients.signers:
            role = signer.role_name
            # We don’t call .list_tabs anymore because that API doesn't work for templates
            has_tabs = (
                hasattr(signer, "tabs")
                and signer.tabs
                and (
                    getattr(signer.tabs, "sign_here_tabs", None)
                    or getattr(signer.tabs, "signHereTabs", None)
                )
            )

            print(f"🔍 {role} tabs: {signer.tabs}")

            if has_tabs:
                print(f"✅ {role} appears to have SignHere tabs.")
                if role == "GSA":
                    gsa_signed = True
            else:
                print(f"❌ {role} has no apparent tabs assigned.")

        if not gsa_signed:
            print("❌ GSA role is missing required signature tab.")
            return False

        return True

    except ApiException as e:
        print(f"❌ Error retrieving template: {e}")
        return False


def update_template_readiness(template, validation_passed: bool):
    """
    Updates the template readiness flag based on validation outcome.

    Args:
        template (DocuSignTemplate): the template to update
        validation_passed (bool): result from validate_signature_roles
    """
    # Ensure required fields are present
    required_fields_present = all(
        [
            template.template_name,
            template.template_id,
            template.signer_role,  # This should be 'GSA'
        ]
    )

    template.is_ready_to_send = required_fields_present and validation_passed
    template.save(update_fields=["is_ready_to_send"])


def docusign_close(request):
    template_id = request.GET.get("template_id")
    template = None
    status = "validating"

    if template_id:
        template = DocuSignTemplate.objects.filter(template_id=template_id).first()

        if template:
            # Kick off validation in background
            validate_template_signature_tabs_task.delay(template_id)
        else:
            status = "notfound"

    return render(
        request,
        "dsign/template_edit_success.html",
        {
            "template": template,
            "status": status,
        },
    )


@login_required
def set_new_hire_template(request, template_id):
    template = get_object_or_404(
        DocuSignTemplate,
        id=template_id,
        employer=request.user.employer,
    )

    if request.method == "POST":
        # ✅ If New Hire checkbox is checked, unset others first
        if 'is_new_hire_template' in request.POST:
            # Unset all other templates first
            DocuSignTemplate.objects.filter(
                employer=request.user.employer,
                is_new_hire_template=True
            ).update(is_new_hire_template=False)
            template.is_new_hire_template = True
        else:
            template.is_new_hire_template = False

        # ✅ In-App Signing is independent
        template.is_in_app_signing_template = 'is_in_app_signing_template' in request.POST
        # Handle company document toggle
        if request.POST.get("is_company_document"):
            template.is_company_document = True
        else:
            template.is_company_document = False

        template.save()
        messages.success(request, "Template updated successfully.")

    return redirect("hr_dashboard")


# Bulk upload of forms to S3 bucket
@user_passes_test(lambda u: u.is_superuser)
def bulk_upload_signed_documents_view(request):
    if request.method == "POST":
        form = MultiSignedDocUploadForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data["user"]
            employer = form.cleaned_data["employer"]
            files = request.FILES.getlist("files")

            folder = uuid.uuid4().hex[:8]
            upload_count = 0

            for uploaded_file in files:
                file_path = f"DOCUMENTS/{employer.name.replace(' ', '_')}/{folder}/{uploaded_file.name}"
                upload_to_linode_object_storage(uploaded_file, file_path)

                SignedDocumentFile.objects.create(
                    user=user,
                    employer=employer,
                    envelope_id=uuid.uuid4().hex[:10],
                    file_name=uploaded_file.name,
                    file_path=file_path,
                )
                upload_count += 1

            messages.success(request, f"Successfully uploaded {upload_count} file(s).")
            return redirect("bulk_upload_signed_documents")

    else:
        form = MultiSignedDocUploadForm()

    return render(request, "dsign/bulk_upload.html", {"form": form})


@login_required
def in_app_signing_dashboard(request):
    employer = request.user.employer

    # Get all templates marked for in-app signing
    templates = DocuSignTemplate.objects.filter(
        employer=employer,
        is_in_app_signing_template=True,
        is_ready_to_send=True,  # Assuming you want only finalized forms
    ).order_by("template_name")

    context = {
        "templates": templates,
    }
    return render(request, "dsign/in_app_signing_dashboard.html", context)


@login_required
def start_in_app_signing(request, template_id):
    template = get_object_or_404(
        DocuSignTemplate,
        id=template_id,
        employer=request.user.employer,
        is_in_app_signing_template=True, 
    )

    envelope_id = create_envelope_for_in_app_signing(
        user=request.user,
        template_id=template.template_id,
        employer=request.user.employer,
    )

    # Build Return URL dynamically
    return_url = f"{settings.SITE_URL}/hr/dashboard/"

    # Get the Signing URL
    signing_url = get_recipient_view_url(
        user=request.user,
        envelope_id=envelope_id,
        return_url=return_url,
    )

    return redirect(signing_url)
