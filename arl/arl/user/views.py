import os

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views import View
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from .forms import CustomUserCreationForm
from .models import CustomUser

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

# function to create an email using sendgrid and tempaltes


def create_email(to_email, subject, name, template_id):
    subject = subject
    message = Mail(
        from_email=os.environ.get('MAIL_DEFAULT_SENDER'),
        to_emails=to_email)
    message.dynamic_template_data = {
            'subject': subject,
            'name': name,
        }
    message.template_id = template_id
    response = sg.send(message)

    # Handle the response and return an appropriate value based on your requirements
    if response.status_code == 202:
        return True
    else:
        print("Failed to send email. Error code:", response.status_code)
        return False
