from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.timezone import now

from arl.msg.helpers import create_master_email
from arl.reclose.forms import RecCloseForm
from arl.user.models import CustomUser
from arl.reclose.tasks import generate_recclose_pdf_task
from django.contrib import messages


@login_required
def rec_close_create_view(request):
    if request.method == "POST":
        form = RecCloseForm(request.POST)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.user_employer = request.user.employer
            instance.timestamp = now()
            instance.save()

            # ✅ Trigger Dropbox PDF upload (Celery)
            try:
                result = generate_recclose_pdf_task.delay(instance.id)
                print(f"🔄 Task triggered? ID: {result.id}")
                messages.success(request, "Rec and Close PDF generation task initiated successfully.")
            except Exception as e:
                messages.error(request, f"An error occurred while generating the PDF: {e}")

            # Get recipients in 'rec_close' group
            recipients = CustomUser.objects.filter(
                groups__name="rec_close", is_active=True
            ).values_list("email", flat=True)

            # Subject includes store number and date
            subject = f"Rec and Close for {instance.store_number} - {instance.timestamp.date()}"

            template_data = {
                "subject": subject,
                "store_number": instance.store_number,
                "shift_number": instance.shift_number,
                "total_sales": float(instance.total_sales),
                "cat_post_host": float(instance.cat_post_host),
                "drive_offs": float(instance.drive_offs),
                "purchases": float(instance.purchases),
                "ppts_redemptions": float(instance.ppts_redemptions),
                "lotto_payout": float(instance.lotto_payout),
                "uber_eats": float(instance.uber_eats),
                "skip": float(instance.skip),
                "drive_off_recovery": float(instance.drive_off_recovery),
                "cash_safe_drops": float(instance.cash_safe_drops),
                "last_safe_drop": float(instance.last_safe_drop),
                "in_brink": float(instance.in_brink),
                "total_section_2": float(instance.total_section_2),
                "over_or_short": float(instance.over_or_short),
                "timestamp": str(instance.timestamp.date()),
            }

            sendgrid_template_id = (
                "d-9ae56177150a49588cea9de1120eb186"
            )  # make sure it's set
            create_master_email(
                to_email=list(recipients),
                sendgrid_id=sendgrid_template_id,
                template_data=template_data,
            )

            return redirect("rec_close_success")
    else:
        form = RecCloseForm()

    return render(request, "reclose/create_reclose.html", {
        "form": form,
        "tank_numbers": ["1", "2", "3", "4"],
        "meter_numbers": ["1", "2", "3", "4"],
    })


def rec_close_success(request):
    return render(request, "reclose/success.html")
