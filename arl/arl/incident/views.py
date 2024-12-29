from io import BytesIO

from django.contrib import messages
from django.contrib.auth.mixins import (LoginRequiredMixin,
                                        PermissionRequiredMixin)
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import ListView
from django.views.generic.edit import CreateView, UpdateView
from PIL import Image
from django.template.loader import render_to_string
from arl.helpers import (get_s3_images_for_incident,
                         upload_to_linode_object_storage)

from .forms import IncidentForm, MajorIncidentForm
from .models import Incident, MajorIncident
from .tasks import (generate_and_send_pdf_task,
                    generate_major_incident_pdf_from_list_task,
                    generate_major_incident_pdf_task,
                    generate_pdf_email_to_user_task, generate_pdf_task,
                    save_incident_file, save_major_incident_file)
import logging

logger = logging.getLogger(__name__)


class IncidentCreateView(PermissionRequiredMixin, LoginRequiredMixin,
                         CreateView):
    model = Incident
    login_url = "/login/"
    permission_required = "incident.add_incident"
    form_class = IncidentForm
    template_name = "incident/create_incident.html"
    success_url = reverse_lazy("home")
    # permission_denied_message = "You are not allowed to add incidents."

    def handle_no_permission(self):
        # Render the custom 403.html template for permission denial
        return render(self.request, "incident/403.html", status=403)

    def dispatch(self, request, *args, **kwargs):
        try:
            # Your print statement for debugging
            print("Dispatch method called.")
            return super().dispatch(request, *args, **kwargs)
        except Exception as e:
            print(f"Exception occurred: {e}")
            raise

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user  # Pass the user to the form
        return kwargs

    def get(self, request, *args, **kwargs):
        form = self.form_class(user=self.request.user)
        return self.render_to_response({"form": form})

    def form_valid(self, form):
        form.instance.user_employer = self.request.user.employer
        form_data = self.serialize_form_data(form.cleaned_data)

        # Trigger the Celery task to save form data
        save_incident_file.delay(**form_data)

        messages.success(
            self.request,
            "PDF generation started. Check your email. The file is attached.",
        )
        return redirect("home")

    def form_invalid(self, form):
        return self.render_to_response({"form": form})

    def serialize_form_data(self, form_data):
        # Convert ForeignKey fields to their primary key values
        form_data["store"] = (
            form_data["store"].pk
            if "store" in form_data and form_data["store"] is not None
            else None
        )
        form_data["user_employer"] = (
            form_data["user_employer"].pk
            if "user_employer" in form_data and form_data["user_employer"] is not None
            else None
        )
        return form_data


class MajorIncidentCreateView(PermissionRequiredMixin, LoginRequiredMixin,
                              CreateView):
    model = MajorIncident
    login_url = "/login/"
    permission_required = "incident.add_major_incident"
    form_class = MajorIncidentForm
    template_name = "incident/create_major_incident.html"
    success_url = reverse_lazy("home")
    # permission_denied_message = "You are not allowed to add incidents."

    def handle_no_permission(self):
        # Render the custom 403.html template for permission denial
        return render(self.request, "incident/403.html", status=403)

    def dispatch(self, request, *args, **kwargs):
        try:
            # Your print statement for debugging
            print("Dispatch method called.")
            return super().dispatch(request, *args, **kwargs)
        except Exception as e:
            print(f"Exception occurred: {e}")
            raise

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user  # Pass the user to the form
        return kwargs

    def get(self, request, *args, **kwargs):
        form = self.form_class(user=self.request.user)
        return self.render_to_response({"form": form})

    def form_valid(self, form):
        form.instance.user_employer = self.request.user.employer
        form_data = self.serialize_form_data(form.cleaned_data)

        # Trigger the Celery task to save form data
        save_major_incident_file.delay(**form_data)

        messages.success(
            self.request,
            "PDF generation started. Check your email. The file is attached.",
        )
        return redirect("home")

    def form_invalid(self, form):
        return self.render_to_response({"form": form})

    def serialize_form_data(self, form_data):
        # Convert ForeignKey fields to their primary key values
        form_data["store"] = (
            form_data["store"].pk
            if "store" in form_data and form_data["store"] is not None
            else None
        )
        form_data["user_employer"] = (
            form_data["user_employer"].pk
            if "user_employer" in form_data and form_data["user_employer"] is not None
            else None
        )
        return form_data


@receiver(post_save, sender=MajorIncident)
def handle_new_major_incident_form_creation(sender, instance, created,
                                            **kwargs):
    if created:
        try:
            generate_major_incident_pdf_task.delay(instance.id)
        except Exception as e:
            print(f"An error occurred: {e}")


@receiver(post_save, sender=Incident)
def handle_new_incident_form_creation(sender, instance, created,
                                      **kwargs):
    if created:
        try:
            # Set the queued_for_sending field to True
            instance.queued_for_sending = True
            instance.save(update_fields=["queued_for_sending"])
            generate_pdf_task.delay(instance.id)
        except Exception as e:
            print(f"An error occurred: {e}")


class QueuedIncidentsListView(ListView):
    model = Incident
    template_name = 'incident/queued_incidents_list.html'
    context_object_name = 'queued_incidents'

    def get_queryset(self):
        queryset = Incident.objects.filter(queued_for_sending=True, sent=False, do_not_send=False)
        print(queryset)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        logger.debug(f"Context Data: {context}")
        print("Context Data:", context) 
        return context


def send_incident_now(request, pk):
    """
    Process the "Send Now" action for an incident and update its status.
    """
    # Fetch the incident object
    incident = get_object_or_404(Incident, pk=pk)

    try:
        # Mark the incident as processed
        incident.queued_for_sending = False
        incident.save(update_fields=["queued_for_sending"])

        # Trigger the task to generate and send the PDF
        generate_and_send_pdf_task.delay(incident.id)

        # Return an empty response to indicate the row should be removed
        return HttpResponse(status=200)  # HTMX will remove the row with "outerHTML:remove"
    except Exception as e:
        # Return an error response as an HTML row for display
        error_html = f"""
        <tr id="incident-{incident.id}">
            <td colspan="5" class="text-danger">Error: {str(e)}</td>
        </tr>
        """
        return HttpResponse(error_html, status=500, content_type="text/html")


def mark_do_not_send(request, pk):
    """
    Marks the incident as "Do Not Send" and removes it from the queue.
    """
    incident = get_object_or_404(Incident, pk=pk)

    try:
        # Mark the incident as "Do Not Send"
        incident.queued_for_sending = False
        incident.sent = False  # Ensure it's not marked as sent
        incident.do_not_send = True  # Add this field in your model if not present
        incident.save(update_fields=["queued_for_sending", "sent", "do_not_send"])
        print(f"Incident {pk} marked as 'Do Not Send'.")
        return HttpResponse(status=200)  # HTMX will remove the row
    except Exception as e:
        print(f"Error processing 'Do Not Send' for incident {pk}: {e}")
        return HttpResponse(status=500)  # Generic error response
    

class IncidentUpdateView(PermissionRequiredMixin, LoginRequiredMixin,
                         UpdateView):
    model = Incident
    login_url = "/login/"
    permission_required = "incident.add_incident"
    form_class = IncidentForm
    template_name = "incident/create_incident.html"
    success_url = reverse_lazy("incident_list")

    def handle_no_permission(self):
        # Render the custom 403.html template for permission denial
        return render(self.request, "incident/403.html", status=403)

    def dispatch(self, request, *args, **kwargs):
        try:
            # Your print statement for debugging
            print("Dispatch method called.")
            return super().dispatch(request, *args, **kwargs)
        except Exception as e:
            print(f"Exception occurred: {e}")
            raise

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        user = self.request.user
        employer = user.employer
        existing_images = []

        # Check if image_folder exists and get available images from S3
        if self.object.image_folder:
            existing_images = get_s3_images_for_incident(
                self.object.image_folder, user.employer
            )
        # print(existing_images)
        form = self.form_class(
            instance=self.object, initial={"existing_images": existing_images}
        )
        form.fields["user_employer"].initial = employer

        return self.render_to_response(
            self.get_context_data(
                form=form, existing_images=existing_images,
                user_employer=employer
            )
        )

    def form_valid(self, form):
        form.instance.user_employer = self.request.user.employer
        return super().form_valid(form)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user"] = self.request.user
        return context


class MajorIncidentUpdateView(PermissionRequiredMixin, LoginRequiredMixin,
                              UpdateView):
    model = MajorIncident
    login_url = "/login/"
    permission_required = "incident.add_incident"
    form_class = MajorIncidentForm
    template_name = "incident/create_major_incident.html"
    success_url = reverse_lazy("major_incident_list")

    def handle_no_permission(self):
        # Render the custom 403.html template for permission denial
        return render(self.request, "incident/403.html", status=403)

    def dispatch(self, request, *args, **kwargs):
        try:
            # Your print statement for debugging
            print("Dispatch method called.")
            return super().dispatch(request, *args, **kwargs)
        except Exception as e:
            print(f"Exception occurred: {e}")
            raise

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        user = self.request.user
        employer = user.employer
        existing_images = []

        # Check if image_folder exists and get available images from S3
        if self.object.image_folder:
            existing_images = get_s3_images_for_incident(
                self.object.image_folder, user.employer
            )
        # print(existing_images)
        form = self.form_class(
            instance=self.object, initial={"existing_images": existing_images}
        )
        form.fields["user_employer"].initial = employer

        return self.render_to_response(
            self.get_context_data(
                form=form, existing_images=existing_images,
                user_employer=employer
            )
        )

    def form_valid(self, form):
        form.instance.user_employer = self.request.user.employer
        return super().form_valid(form)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user"] = self.request.user
        return context


class ProcessIncidentImagesView(PermissionRequiredMixin,
                                LoginRequiredMixin, View):
    login_url = "/login/"
    permission_required = "incident.add_incident"
    raise_exception = True  # Raise exception when no access
    # instead of redirect
    permission_denied_message = "You are not allowed to add incidents."

    def post(self, request, *args, **kwargs):
        if request.method == "POST":
            user = request.user  # Authenticated user
            # print(user.employer)
            image_folder = request.POST.get("image_folder")
            # print(image_folder)
            employer = user.employer
            # Process the uploaded files here
            uploaded_files = request.FILES.getlist(
                "file"
            )  # 'file' is the field name used by Dropzone
            for uploaded_file in uploaded_files:
                # print(uploaded_file.name)
                file = uploaded_file
                folder_name = f"SITEINCIDENT/{employer}/{image_folder}/"
                filename = uploaded_file.name
                employee_key = "{}/{}".format(folder_name, filename)
                # print(employee_key)
                # Open the uploaded image using Pillow
                image = Image.open(file)
                # Resize the image to a larger thumbnail size, e.g.,
                # 1000x1000 pixels
                thumbnail_size = (1500, 1500)
                image.thumbnail(thumbnail_size, Image.LANCZOS)
                # Resize the image to your desired dimensions (e.g., 1000x1000)
                # resized_image = image.resize((500, 500), Image.LANCZOS)
                # print(image)
                # Save the resized image to a temporary BytesIO object
                temp_buffer = BytesIO()
                image.save(temp_buffer, format="JPEG")
                temp_buffer.seek(0)
                # Upload the resized image to Linode Object Storage
                upload_to_linode_object_storage(temp_buffer, employee_key)
                # Close the temporary buffer
                temp_buffer.close()
                # Process and save the files to the desired location
                # You can use the uploaded_files list to iterate through
                # the files and save them

                # Return a JSON response indicating success
            return JsonResponse({"message": "Files uploaded successfully"})
        else:
            # Handle GET request or other methods
            return JsonResponse({"message": "Invalid request method"})


# This route is used to generate a pdf from a newly created
# incident form. It calls a task to upload and email
# the incident form


def generate_pdf(request, incident_id):
    user_email = request.user.email
    generate_pdf_task.delay(incident_id, user_email)
    messages.success(request, "PDF generation started. HR will receive copy")
    return redirect("home")


def generate_major_incident_pdf(request, incident_id):
    user_email = request.user.email
    print(user_email, incident_id)
    generate_major_incident_pdf_from_list_task.delay(incident_id, user_email)
    messages.success(request, "PDF generation started. HR will receive copy")
    return redirect("home")

# This route is used to generate a pdf and
# email it to the user


def generate_incident_pdf_email(request, incident_id):
    user_email = request.user.email
    generate_pdf_email_to_user_task.delay(incident_id, user_email)
    messages.success(
        request, "PDF generation started. Check your email. The file is attached."
    )
    return redirect("home")


def generate_pdf_web(request, incident_id):
    # Fetch incident data based on incident_id
    try:
        incident = MajorIncident.objects.get(pk=incident_id)
    except ObjectDoesNotExist:
        raise ValueError("Incident with ID {} does not exist."
                         .format(incident_id))

    images = get_s3_images_for_incident(incident.image_folder,
                                        incident.user_employer)
    context = {"incident": incident, "images": images}
    return render(request, "incident/major_incident_form_pdf.html", context)


class IncidentListView(PermissionRequiredMixin, ListView):
    model = Incident
    template_name = "incident/incident_list.html"
    context_object_name = "incidents"
    permission_required = "incident.view_incident"
    raise_exception = True
    permission_denied_message = "You are not allowed to view incidents."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["defer_render"] = True
        # Pass defer_render as context to the template
        return context


class MajorIncidentListView(PermissionRequiredMixin, ListView):
    model = MajorIncident
    template_name = "incident/major_incident_list.html"
    context_object_name = "incidents"
    permission_required = "incident.view_incident"
    raise_exception = True
    permission_denied_message = "You are not allowed to view incidents."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["defer_render"] = True
        # Pass defer_render as context to the template
        return context


def Permission_Denied_View(request, exception):
    def get(self, request, exception):
        return render(request, "incident/403.html", status=403)
