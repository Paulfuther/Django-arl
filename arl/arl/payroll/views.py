from django.shortcuts import render
from datetime import timedelta
from .models import CalendarEvent, PayPeriod, StatutoryHoliday, PayrollInfo
from arl.user.models import Store


def payroll_calendar_view(request):
    events = CalendarEvent.objects.order_by('date')
    return render(request, 'payroll/calendar.html', {'events': events})


def payroll_entry_view(request):
    # Get pay periods for dropdown
    pay_periods = PayPeriod.objects.order_by('-start_date')
    stores = Store.objects.all()

    selected_pay_period = None
    selected_store = None
    employees = []
    table_data = []

    if request.method == 'GET':
        pay_period_id = request.GET.get('pay_period')
        store_id = request.GET.get('store')

        if pay_period_id:
            selected_pay_period = PayPeriod.objects.get(id=pay_period_id)
            selected_store = store_id

            # Get all employees in the selected store
            employees = PayrollInfo.objects.filter(user__store=store_id)

            # Generate table data for the selected pay period
            start_date = selected_pay_period.start_date
            end_date = selected_pay_period.end_date
            days = (end_date - start_date).days + 1

            for employee in employees:
                row = {
                    "employee": employee.user.get_full_name(),
                    "days": [
                        {
                            "date": (start_date + timedelta(days=i)),
                            "day_of_week": (start_date + timedelta(days=i)).strftime('%A'),
                            "hours": None,  # Default hours input
                        }
                        for i in range(days)
                    ],
                }
                table_data.append(row)

    return render(request, 'payroll/entry.html', {
        'pay_periods': pay_periods,
        'stores': stores,
        'employees': employees,
        'table_data': table_data,
        'selected_pay_period': selected_pay_period,
        'selected_store': selected_store,
    })