from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    phone_number = models.CharField(max_length=20)
    mon_avail = models.CharField(max_length=20, null=True)
    tue_avail = models.CharField(max_length=20, null=True)
    wed_avail = models.CharField(max_length=20, null=True)
    thu_avail = models.CharField(max_length=20, null=True)
    fri_avail = models.CharField(max_length=20, null=True)
    sat_avail = models.CharField(max_length=20, null=True)
    sun_avail = models.CharField(max_length=20, null=True)
    # Any additional fields or methods you need

    def __str__(self):
        return self.first_name

