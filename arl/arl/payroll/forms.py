from django import forms
from datetime import timedelta
from .models import PayPeriod, PayrollEntry

class PayrollEntryForm(forms.Form):
    def __init__(self, *args, **kwargs):
        employees = kwargs.pop('employees')  # List of employees
        pay_period = kwargs.pop('pay_period')  # Pay period object
        super().__init__(*args, **kwargs)

        # Dynamically create fields for each employee and date
        start_date = pay_period.start_date
        end_date = pay_period.end_date

        for employee in employees:
            for date in (start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)):
                field_name = f"hours-{employee.id}-{date}"
                self.fields[field_name] = forms.DecimalField(
                    max_digits=5,
                    decimal_places=2,
                    required=False,
                    widget=forms.NumberInput(attrs={'placeholder': 'Hours worked'}),
                    label=f"{employee} on {date}"
                )
    
    def save(self, employees, pay_period):
        """Save or update payroll entries for each employee and date."""
        for employee in employees:
            for date in (pay_period.start_date + timedelta(days=i) for i in range((pay_period.end_date - pay_period.start_date).days + 1)):
                field_name = f"hours-{employee.id}-{date}"
                hours_worked = self.cleaned_data.get(field_name)
                if hours_worked is not None:
                    PayrollEntry.objects.update_or_create(
                        employee=employee,
                        pay_period=pay_period,
                        date=date,
                        defaults={"hours_worked": hours_worked},
                    )