from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    phone_number = models.CharField(max_length=20)

    # Any additional fields or methods you need

    def __str__(self):
        return self.first_name

