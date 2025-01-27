from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import CarwashStatusForm
from .models import CarwashStatus


@login_required
def carwash_status_view(request):
    if request.method == 'POST':
        # Pass the logged-in user to the form
        form = CarwashStatusForm(request.POST, user=request.user)
        if form.is_valid():
            status = form.save(commit=False)  # Get the form instance but don't save yet
            status.updated_by = request.user  # Set the updater to the logged-in user
            status.save()  # Save the instance to the database
            return redirect('carwash_status')  # Redirect to the same page after submission
    else:
        form = CarwashStatusForm(user=request.user) # Pass the user to filter stores

    return render(request, 'carwash/carwash_status.html', {'form': form})


@login_required
def carwash_status_list_view(request):
    # Query all entries for the logged-in user's managed stores
    entries = CarwashStatus.objects.filter(store__carwash=True)
    return render(request, 'carwash/carwash_status_list.html', {'entries': entries})