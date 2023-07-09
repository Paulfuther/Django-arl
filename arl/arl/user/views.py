from django.shortcuts import render, redirect
from .forms import CustomUserCreationForm
from django.http import JsonResponse
from django.views import View
from .models import CustomUser


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