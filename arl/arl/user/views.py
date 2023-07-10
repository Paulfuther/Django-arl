from django.shortcuts import render, redirect
from .forms import CustomUserCreationForm
from django.http import JsonResponse
from django.views import View
from .models import CustomUser
from django.core.mail import EmailMessage, send_mail
from django.http import HttpResponse
import os


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        print(form.data)
      
        if form.is_valid():
            verified_phone_number = request.POST.get('phone_number')
            print(verified_phone_number)
            user = form.save(commit=False)
            user.phone_number = verified_phone_number
            user.save()

            msg = EmailMessage(
                from_email=os.environ.get('MAIL_DEFAULT_SENDER'),
                to=['paul.futher@gmail.com'],
            )
            msg.template_id = os.environ.get('SENDGRID_NEWHIRE_ID')
            msg.send(fail_silently=False)

            # Handle successful registration, e.g., redirect to login page
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


def send_email_view(request):
    subject = 'Test Email'
    message = 'This is a test email'
    from_email = os.environ.get('MAIL_DEFAULT_SENDER'),
    recipient_list = ['paul.futher@gmail.com']

    send_mail(subject, message, from_email, recipient_list)
    return HttpResponse('Email sent successfully')