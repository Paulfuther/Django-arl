import json
import logging

from celery.result import AsyncResult
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin

from django.shortcuts import redirect, get_object_or_404
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from .helpers import get_docusign_edit_url
from arl.dsign.helpers import (get_docusign_envelope,
                               get_docusign_template_name_from_template,
                               create_docusign_document)

from arl.dsign.tasks import (get_outstanding_docs,
                             list_all_docusign_envelopes_task)
from .models import DocuSignTemplate
from .forms import NameEmailForm

from .tasks import (create_docusign_envelope_task, process_docusign_webhook,
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
                request, f"Thank you. The document '{template_name}' has been sent to {recipient.get_full_name()}."
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
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Handle the AJAX request to fetch the outstanding documents
        result = get_outstanding_docs.delay()
        envelopes = result.get(timeout=10)  # Adjust the timeout as needed
        return JsonResponse({'outstanding_envelopes': envelopes})
    # Render the template for the initial page load
    return render(request, 'dsign/waiting_for_others.html')


@login_required
def create_new_document_page(request):
    """Handles creating a new DocuSign document and saving it in Django."""

    if request.method == "POST":
        template_name = request.POST.get("template_name", "New Document")
        print("Template Name :", template_name)
        template_id = create_docusign_document(user=request.user, template_name=template_name)

        if template_id:
            messages.success(request, f"Document '{template_name}' created successfully!")
            # ✅ Get the edit URL for the new template
            edit_url = get_docusign_edit_url(template_id)

            if edit_url:
                return redirect(edit_url)  # ✅ Immediately open the DocuSign editor
            else:
                messages.error(request, "Could not retrieve the edit URL. Please try manually.")
        else:
            messages.error(request, "Failed to create a new document.")

        return redirect("hr_dashboard")  # Redirect to HR dashboard

    return render(request, "dsign/create_document.html")


@login_required
def edit_document_page(request, template_id):
    """Loads an HTML page with an iframe for the DocuSign template editor."""
    edit_url = get_docusign_edit_url(template_id)
    user_agent = request.META.get("HTTP_USER_AGENT", "").lower()

    is_safari = "safari" in user_agent and "chrome" not in user_agent and "chromium" not in user_agent

    if is_safari:
        return redirect(edit_url)  # Open DocuSign editor in a new tab for Safari

    return render(request, "dsign/dsign_embed.html", {"edit_url": edit_url})


def docusign_close(request):
    """Redirects users back to your app after they finish editing."""
    return redirect("/")


@login_required
def set_new_hire_template(request, template_id):
    template = get_object_or_404(DocuSignTemplate, id=template_id, employer=request.user.employer)

    # Unset previous
    DocuSignTemplate.objects.filter(employer=request.user.employer).update(is_new_hire_template=False)

    # Set selected
    template.is_new_hire_template = True
    template.save()

    return redirect("hr_dashboard") 