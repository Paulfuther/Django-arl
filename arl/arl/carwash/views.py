from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
import json
from .forms import CarwashStatusForm
from .models import CarwashStatus
from .tasks import generate_carwash_status_report
from django.utils.safestring import mark_safe


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


@login_required
def carwash_status_report(request):
    """Trigger Celery task and fetch carwash status report."""
    task = generate_carwash_status_report.delay()
    report_data = json.loads(task.get(timeout=30))  # ✅ Ensure proper JSON
    
    # ✅ DEBUG: Print the data in console to verify the structure
    # print("🚀 Report Data:", json.dumps(report_data, indent=4))

    return render(request, "carwash/carwash_status_report.html", {"data": report_data})