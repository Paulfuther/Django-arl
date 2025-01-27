from django.conf import settings
from django.db import models
from django.utils.timezone import now

from arl.user.models import (CustomUser,  # Replace with your store app's name
                             Store)


class CarwashStatus(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
    ]

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="carwash_statuses")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    reason = models.TextField(blank=True, null=True)
    date_time = models.DateTimeField(default=now)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)


    def __str__(self):
        return f"Store {self.store.number} - {self.status.capitalize()} - {self.date_time.strftime('%Y-%m-%d %H:%M:%S')}"
