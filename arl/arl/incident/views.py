from io import BytesIO

from django.contrib import messages
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic.edit import CreateView, UpdateView
from django.views.generic.list import ListView
from PIL import Image

from arl.helpers import get_s3_images_for_incident, upload_to_linode_object_storage
from arl.tasks import generate_pdf_task

from .forms import IncidentForm
from .models import Incident


class IncidentCreateView(PermissionRequiredMixin, LoginRequiredMixin, CreateView):
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
        response = super().form_valid(form)

        # Trigger the create_pdf_file_task asynchronously
        generate_pdf_task.delay(self.object.id, self.request.user.email)

        messages.success(
            self.request,
            "PDF generation started. Check your email. The file is attached.",
        )
        return redirect("home")

    def form_invalid(self, form):
        return self.render_to_response({"form": form})


class IncidentUpdateView(PermissionRequiredMixin, LoginRequiredMixin, UpdateView):
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
                form=form, existing_images=existing_images, user_employer=employer
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


class ProcessIncidentImagesView(PermissionRequiredMixin, LoginRequiredMixin, View):
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


def generate_pdf(request, incident_id):
    user_email = request.user.email
    generate_pdf_task.delay(incident_id, user_email)
    messages.success(
        request, "PDF generation started. Check your email. The file is attached."
    )
    return redirect("home")


def generate_pdf_web(request, incident_id):
    # Fetch incident data based on incident_id
    try:
        incident = Incident.objects.get(pk=incident_id)
    except ObjectDoesNotExist:
        raise ValueError("Incident with ID {} does not exist.".format(incident_id))

    images = get_s3_images_for_incident(incident.image_folder, incident.user_employer)
    context = {"incident": incident, "images": images}
    return render(request, "incident/incident_form_pdf.html", context)


class IncidentListView(PermissionRequiredMixin, ListView):
    model = Incident
    template_name = "incident/incident_list.html"
    context_object_name = "incidents"
    permission_required = "incident.view_incident"
    raise_exception = True
    permission_denied_message = "You are not allowed to view incidents."


def Permission_Denied_View(request, exception):
    def get(self, request, exception):
        return render(request, "incident/403.html", status=403)
