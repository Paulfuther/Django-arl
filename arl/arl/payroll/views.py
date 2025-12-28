from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from arl.payroll.models import PayPeriod, PayrollEntry, CustomUser


def payroll_entry_view(request, pay_period_id):
    # Get the pay period
    pay_period = get_object_or_404(PayPeriod, id=pay_period_id)
    start_date = pay_period.start_date
    end_date = pay_period.end_date

    # Get employees and their stores
    employees = CustomUser.objects.filter(
        store__isnull=False
    )  # Adjust filter as needed.

    # Handle form submission
    if request.method == "POST":
        for employee in employees:
            for date in (
                start_date + timedelta(days=i)
                for i in range((end_date - start_date).days + 1)
            ):
                hours_worked = request.POST.get(f"hours-{employee.id}-{date}")
                if hours_worked:
                    # Save or update payroll entry
                    PayrollEntry.objects.update_or_create(
                        employee=employee,
                        store=employee.store,
                        pay_period=pay_period,
                        date=date,
                        defaults={"hours_worked": hours_worked},
                    )
        return HttpResponseRedirect(request.path)  # Redirect to clear POST data.

    # Prepare data for the form
    payroll_data = {}
    for employee in employees:
        payroll_data[employee] = []
        for date in (
            start_date + timedelta(days=i)
            for i in range((end_date - start_date).days + 1)
        ):
            entry = PayrollEntry.objects.filter(
                employee=employee, pay_period=pay_period, date=date
            ).first()
            payroll_data[employee].append(entry.hours_worked if entry else None)

    # Render the template
    return render(
        request,
        "payroll/payroll_entry.html",
        {
            "pay_period": pay_period,
            "employees": employees,
            "payroll_data": payroll_data,
            "dates": [
                start_date + timedelta(days=i)
                for i in range((end_date - start_date).days + 1)
            ],
        },
    )
