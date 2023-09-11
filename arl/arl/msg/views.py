from django.shortcuts import render, redirect
from .forms import SMSForm
from arl.tasks import send_sms_task  # Import your send_sms_task function
from django.http import HttpResponse


def send_sms_view(request):
    if request.method == 'POST':
        form = SMSForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data['phone_number']
            # Call the send_sms_task asynchronously
            send_sms_task.delay(phone_number)

            return HttpResponse("success")
    else:
        form = SMSForm()

    return render(request, 'msg/sms_form.html', {'form': form})
