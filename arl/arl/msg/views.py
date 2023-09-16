import json


from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from arl.tasks import send_sms_task  # Import your send_sms_task function
from arl.user.models import CustomUser

from .forms import SMSForm
from .models import EmailEvent


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


@csrf_exempt  # In production, use proper CSRF protection.
def sendgrid_webhook(request):
    if request.method == 'POST':
        try:
            payload = json.loads(request.body.decode('utf-8'))
            if isinstance(payload, list) and len(payload) > 0:
                # Extract the first (and only) item from the list
                event_data = payload[0]
                email = event_data.get('email', '')
                event = event_data.get('event', '')
                ip = event_data.get('ip', '')
                sg_event_id = event_data.get('sg_event_id', '')
                sg_message_id = event_data.get('sg_message_id', '')
                sg_template_id = event_data.get('sg_template_id', '')
                sg_template_name = event_data.get('sg_template_name', '')
                timestamp = timezone.datetime.fromtimestamp(event_data.get('timestamp', 0),
                                                            tz=timezone.utc)
                url = event_data.get('url', '')
                useragent = event_data.get('useragent', '')

                # Find the user by email address in your custom user model
                try:
                    user = CustomUser.objects.get(email=email)
                except CustomUser.DoesNotExist:
                    user = None

                username = user.username if user else None

                # Create and save the EmailEvent instance
                event = EmailEvent(
                    email=email,
                    event=event,
                    ip=ip,
                    sg_event_id=sg_event_id,
                    sg_message_id=sg_message_id,
                    sg_template_id=sg_template_id,
                    sg_template_name=sg_template_name,
                    timestamp=timestamp,
                    url=url,
                    user=user,  # Set the user associated with this email event
                    username=username,
                    useragent=useragent,
                )
                event.save()

                return JsonResponse({'message': 'Webhook received successfully'}, status=200)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON payload'}, status=400)
    else:
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)
