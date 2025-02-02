from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.timezone import now

from arl.user.models import CustomUser  # Replace with your store app's name
from arl.user.models import Store


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

    def clean(self):
        # Fetch the last saved record for the same store
        last_status = CarwashStatus.objects.filter(store=self.store).order_by('-date_time').first()

        # Allow saving if no previous status exists
        if not last_status:
            return

        # ✅ ALLOW UPDATES: If the object already exists and we're only updating the reason, don't block it.
        if self.pk and last_status.status == self.status:
            return  # No validation error if updating only the reason

        # ❌ BLOCK DUPLICATE STATUS: If it's a new entry or status change, check for duplicates.
        if last_status.status == self.status:
            raise ValidationError(f"The store is already marked as {self.status}.")

    def save(self, *args, **kwargs):
        self.clean()  # Ensure validation is checked before saving
        super().save(*args, **kwargs)
