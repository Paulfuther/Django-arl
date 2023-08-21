

from io import BytesIO

import pdfkit
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from PIL import Image

from arl.helpers import (get_s3_images_for_incident,
                         upload_to_linode_object_storage)

from .forms import IncidentForm
from .models import Incident


def create_incident(request):
    if request.method == 'POST':
        form = IncidentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('home')  # Redirect to a view that lists incidents
    else:
        form = IncidentForm()
    return render(request, 'incident/create_incident.html', {'form': form})


def update_incident(request, incident_id):
    incident = get_object_or_404(Incident, pk=incident_id)
    if request.method == 'POST':
        form = IncidentForm(request.POST, instance=incident)
        if form.is_valid():
            form.save()
            return redirect('incident_list')  # Redirect to a view that lists incidents
    else:
        form = IncidentForm(instance=incident)
    return render(request, 'update_incident.html', {'form': form})


# @login_required
def process_incident_images(request):
    if request.method == 'POST':
        user = request.user  # Authenticated user
        print(user.employer)
        random_number = request.POST.get('random_number')
        employer = user.employer  # Assuming user.profile holds profile information
        # Process the uploaded files here
        uploaded_files = request.FILES.getlist('file')  # 'file' is the field name used by Dropzone
        for uploaded_file in uploaded_files:
            print(uploaded_file.name)
            file = uploaded_file
            folder_name = f'SITEINCIDENT/{employer}/{random_number}/'
            filename = uploaded_file.name
            employee_key = '{}/{}'.format(folder_name, filename)
            print(employee_key)
            # Open the uploaded image using Pillow
            image = Image.open(file)
            # Resize the image to a larger thumbnail size, e.g., 1000x1000 pixels
            thumbnail_size = (1500, 1500)
            image.thumbnail(thumbnail_size, Image.LANCZOS)
            # Resize the image to your desired dimensions (e.g., 1000x1000)
            # resized_image = image.resize((500, 500), Image.LANCZOS)
            print(image)
            # Save the resized image to a temporary BytesIO object
            temp_buffer = BytesIO()
            image.save(temp_buffer, format='JPEG')
            temp_buffer.seek(0)
            # Upload the resized image to Linode Object Storage
            upload_to_linode_object_storage(temp_buffer, employee_key)
            # Close the temporary buffer
            temp_buffer.close()

        # Process and save the files to the desired location
        # You can use the uploaded_files list to iterate through the files and save them

        # Return a JSON response indicating success
        return JsonResponse({'message': 'Files uploaded successfully'})
    else:
        # Handle GET request or other methods
        return JsonResponse({'message': 'Invalid request method'})


def incident_form_pdf(request, incident_id):
    user = request.user  # Authenticated user
    incident = Incident.objects.get(pk=incident_id)  # Get the incident
    print(incident.pk)
    images = get_s3_images_for_incident(incident.image_folder, user.employer)
    print(incident.image_folder)
    context = {
        'incident': incident,
        'images': images,
    }

    return render(request, 'incident/incident_form_pdf.html', context)


def generate_pdf(request, incident_id):
    user = request.user
    #  Fetch incident data based on incident_id
    incident = Incident.objects.get(pk=incident_id)  # Get the incident
    images = get_s3_images_for_incident(incident.image_folder, user.employer)
    context = {'incident': incident, 'images': images}  # Add more context as needed
    html_content = render_to_string('incident/incident_form_pdf.html', context)

    #  Generate the PDF using pdfkit
    options = {
            'enable-local-file-access': None,
            '--keep-relative-links': '',
            'encoding': "UTF-8",
        }
    pdf = pdfkit.from_string(html_content, False, options)

    #  Create a BytesIO object to store the PDF content
    pdf_buffer = BytesIO(pdf)

    #  Set the BytesIO buffer's position to the beginning
    pdf_buffer.seek(0)

    #  Create an HTTP response with PDF content
    response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="incident_report.pdf"'

    #  Close the BytesIO buffer to free up resources
    pdf_buffer.close()

    return response
