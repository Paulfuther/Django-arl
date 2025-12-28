from django.db import models
from arl.user.models import CustomUser, Store


class PayPeriod(models.Model):
    name = models.CharField(max_length=100, null=True)
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date})"


class StatutoryHoliday(models.Model):
    date = models.DateField(unique=True)  # Holiday date
    name = models.CharField(max_length=100)  # Name of the holiday
    pay_period = models.ForeignKey(
        PayPeriod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="holidays",
    )

    def __str__(self):
        return f"{self.name} on {self.date}"


class CalendarEvent(models.Model):
    EVENT_TYPES = [
        ("PAY", "Pay Day"),
        ("HOLIDAY", "Statutory Holiday"),
        ("OTHER", "Other"),
    ]
    date = models.DateField()
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.get_event_type_display()} on {self.date}"


class PayrollEntry(models.Model):
    employee = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    pay_period = models.ForeignKey(PayPeriod, on_delete=models.CASCADE)
    date = models.DateField()  # One entry per day per employee.
    hours_worked = models.DecimalField(max_digits=5, decimal_places=2)
    overtime_hours = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    notes = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ("employee", "store", "pay_period", "date")

    def __str__(self):
        return f"{self.employee} - {self.date} ({self.hours_worked} hrs)"
