import json
import logging

from celery.result import AsyncResult
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from arl.dsign.helpers import (get_docusign_envelope,
                               get_docusign_template_name_from_template)
from arl.dsign.models import DocuSignTemplate
from arl.dsign.tasks import (get_outstanding_docs,
                             list_all_docusign_envelopes_task)

from .forms import NameEmailForm
from .models import ProcessedDocsignDocument
from .tasks import (create_docusign_envelope_task, process_docusign_webhook,
                    send_new_hire_quiz)

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
            d_name = form.cleaned_data["name"]
            d_email = form.cleaned_data["email"]
            ds_template = form.cleaned_data.get("template_id")
            print(ds_template, d_name, d_email)
            # Fetch the template name based on the ID
            template = form.cleaned_data["template_name"]
            template_name = template.template_name if template else "Unknown Template"
            envelope_args = {
                "signer_email": d_email,
                "signer_name": d_name,
                "template_id": ds_template,
            }

            print("Here are the args:", envelope_args)

            create_docusign_envelope_task.delay(envelope_args)

            messages.success(
                request, f"Thank you. The document '{template_name}' has been sent."
            )
            return redirect("home")
        else:
            return render(request, "dsign/name_email_form.html", {"form": form})


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


@receiver(post_save, sender=ProcessedDocsignDocument)
def post_save_processed_docsign_document(sender, instance, created, **kwargs):
    if created and instance.template_name == "New Hire File":
        print("A New Hire File was created")

        # Check if a New Hire Quiz has already been sent to this user
        if not ProcessedDocsignDocument.objects.filter(
            user=instance.user, template_name="New_Hire_Quiz"
        ).exists():
            try:
                # Attempt to find the "New_Hire_Quiz" template
                new_hire_quiz_template = DocuSignTemplate.objects.get(
                    template_name="New_Hire_Quiz"
                )
                new_hire_quiz_template_id = new_hire_quiz_template.template_id
                print(new_hire_quiz_template_id)
            except DocuSignTemplate.DoesNotExist:
                # Handle the case where the template does not exist
                print("New Hire Quiz template not found.")
                return  # Exit the function if the template is not found

            try:
                # Fetch the Store instance related to the user
                user_store = instance.user.store

                if user_store and user_store.manager:
                    manager_email = user_store.manager.email
                    manager_name = user_store.manager.get_full_name()

                else:
                    # Default manager details if no manager is assigned to the store
                    manager_email = "paul.futher@gmail.com"
                    manager_name = "Paul Futher"

                print("Manager Email:", manager_email)
                print("Manager Name:", manager_name)
                print("User Store:", user_store)
            except Exception as e:
                print("An unexpected error occurred:", str(e))
                # Default manager details if an unexpected error occurs
                manager_email = "paul.futher@gmail.com"
                manager_name = "Paul Futher"
                print("Default Manager Email:", manager_email)
                print("Default Manager Name:", manager_name)

            # Construct the envelope_args
            envelope_args = {
                "signer_email": instance.user.email,
                "signer_name": instance.user.get_full_name(),
                "template_id": new_hire_quiz_template_id,
                "manager_email": manager_email,
                "manager_name": manager_name,
            }
            print("Envelope Args:", envelope_args)
            # Call the Celery task with the constructed arguments
            send_new_hire_quiz.delay(envelope_args)
        else:
            print(
                f"User {instance.user.get_full_name()} has already been sent a New Hire Quiz."
            )
    else:
        # If the document is not a New Hire File, exit the function
        print("The saved document is not a New Hire File. Exiting.")


@login_required
def waiting_for_others_view(request):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Handle the AJAX request to fetch the outstanding documents
        result = get_outstanding_docs.delay()
        envelopes = result.get(timeout=10)  # Adjust the timeout as needed
        return JsonResponse({'outstanding_envelopes': envelopes})
    # Render the template for the initial page load
    return render(request, 'dsign/waiting_for_others.html')