from django.db import models
from datetime import timedelta
from arl.user.models import CustomUser, Store


class PayPeriod(models.Model):
    start_date = models.DateField()  # Start of the pay period
    end_date = models.DateField()    # End of the pay period
    total_hours_worked = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    gross_pay = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    net_pay = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"Pay Period: {self.start_date} to {self.end_date}"

    @classmethod
    def get_current_pay_period(cls):
        """Determine the current pay period based on today's date."""
        from datetime import date
        today = date.today()
        if 1 <= today.day <= 15:
            start = today.replace(day=1)
            end = today.replace(day=15)
        else:
            start = today.replace(day=16)
            # Handle end-of-month correctly
            next_month = (today.month % 12) + 1
            end = today.replace(month=next_month, day=1) - timedelta(days=1)
        return cls.objects.get_or_create(start_date=start, end_date=end)


class StatutoryHoliday(models.Model):
    date = models.DateField(unique=True)  # Holiday date
    name = models.CharField(max_length=100)  # Name of the holiday
    pay_period = models.ForeignKey(PayPeriod, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name="holidays")

    def __str__(self):
        return f"{self.name} on {self.date}"


class CalendarEvent(models.Model):
    EVENT_TYPES = [
        ('PAY', 'Pay Day'),
        ('HOLIDAY', 'Statutory Holiday'),
        ('OTHER', 'Other'),
    ]
    date = models.DateField()
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.get_event_type_display()} on {self.date}"


class PayrollInfo(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    store = models.ForeignKey('user.Store', on_delete=models.CASCADE, related_name='payroll_info')
    salary = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    hourly_rate = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.store.name}"