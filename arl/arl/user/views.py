import os

from django.contrib.auth.models import Group
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views import View
from twilio.base.exceptions import TwilioException

from arl.msg.helpers import (check_verification_token, create_bulk_sms,
                             create_email, request_verification_token,
                             send_sms)

from .forms import CustomUserCreationForm
from .models import CustomUser, Employer


def register(request):
    employers = Employer.objects.all()  # Retrieve all employers from the database
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        print(form.data)    
        if form.is_valid():
            verified_phone_number = request.POST.get('phone_number')
            print(verified_phone_number)
            user = form.save(commit=False)
            user.phone_number = verified_phone_number
            user.save()
            create_email(user.email, 'Welcome Aboard', user.first_name,
                         os.environ.get('SENDGRID_NEWHIRE_ID'))
            gsa_group = Group.objects.get(name='GSA')
            user.groups.add(gsa_group)
            
            return redirect('/')
    else:
        form = CustomUserCreationForm()
        print(form.errors)
    return render(request, 'user/index.html', {'form': form, 'Employer': employers})


class CheckPhoneNumberUniqueView(View):
    def post(self, request):
        phone_number = request.POST.get('phone_number')
        print(phone_number)
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
 

def request_verification(request):
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')
        print('Phone number:', phone_number)  # Debugging statement
        try:
            # Request the verification code from Twilio
            request_verification_token(phone_number)
            # Verification request successful  
            # Return a success response
            return JsonResponse({'success': True})
        except TwilioException:
            # Handle TwilioException if verification request fails
            return JsonResponse({'success': False, 'error': 'Failed to send verification code'})
    # Return an error response for unsupported request methods
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


def check_verification(request):
    if request.method == 'POST':
        phone = request.POST.get('phone_number')
        token = request.POST.get('verification_code')
        print('Phone number:', phone)
        print('Verification code:', token)
        print(phone, token)
        try:
            if check_verification_token(phone, token):
                return JsonResponse({'success': True})
        except TwilioException:
            return JsonResponse({'success': False, 'error': 'Failed to send verification code'})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})
