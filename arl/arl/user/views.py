import os

from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views import View
from sendgrid import SendGridAPIClient

from arl.msg.helpers import create_bulk_sms, create_email, send_sms

from .forms import CustomUserCreationForm
from .models import CustomUser

sender_email = os.environ.get("MAIL_DEFAULT_SENDER")
sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        print(form.data)    
        if form.is_valid():
            verified_phone_number = request.POST.get('phone_number')
            print(verified_phone_number)
            user = form.save(commit=False)
            user.phone_number = verified_phone_number
            create_email(user.email, 'Welcome Aboard', user.first_name,
                         os.environ.get('SENDGRID_NEWHIRE_ID'))
            user.save()
            return redirect('/')
    else:
        form = CustomUserCreationForm()
        print(form.errors)
    return render(request, 'user/index.html', {'form': form})


class CheckPhoneNumberUniqueView(View):
    def post(self, request):
        phone_number = request.POST.get('phone_number')

        if CustomUser.objects.filter(phone_number=phone_number).exists():
            return JsonResponse({'exists': True})
        else:
            return JsonResponse({'exists': False})         


def sms_form(request):
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')
        if phone_number:
            # Call the send_sms function with the phone_number
            send_sms(phone_number)
            # Optionally, you can redirect to a success page or display a success message
            return render(request, 'msg/success.html')
    else:
        # Display the form for GET requests
        return render(request, 'msg/sms_form.html')


def send_bulk_sms(request):
    if request.method == 'POST':
        create_bulk_sms(request)
        return HttpResponse('Bulk SMS sent successfully.')  # or redirect to a success page  
    else:
        return render(request, 'msg/sms_form.html')
