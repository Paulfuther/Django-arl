from django.contrib.auth.models import AbstractUser
from django.core.validators import (MaxLengthValidator, MinLengthValidator,
                                    RegexValidator)
from phonenumber_field.modelfields import PhoneNumberField
from django_countries.fields import CountryField
from django.db import models


class Employer(models.Model):
    name = models.CharField(max_length=100)
    # Add any additional fields for the employer
    address = models.CharField(max_length=100, null=True)
    address_two = models.CharField(max_length=100, null=True)
    city = models.CharField(max_length=100, null=True)
    state_province = models.CharField(max_length=100, null=True)
    country = CountryField(null=True)
    phone_number = PhoneNumberField(null=True)
    created = models.DateTimeField(auto_now_add=True, null=True)
    updated = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return self.name


class CustomUser(AbstractUser):
    phone_number = models.CharField(max_length=20)
    sin = models.CharField(
        max_length=9,
        validators=[
            MinLengthValidator(9),
            MaxLengthValidator(9),
            RegexValidator(r'^\d{9}$', 'SIN number must be 9 digits')
        ], null=True
    )
    mon_avail = models.CharField(max_length=20, null=True)
    tue_avail = models.CharField(max_length=20, null=True)
    wed_avail = models.CharField(max_length=20, null=True)
    thu_avail = models.CharField(max_length=20, null=True)
    fri_avail = models.CharField(max_length=20, null=True)
    sat_avail = models.CharField(max_length=20, null=True)
    sun_avail = models.CharField(max_length=20, null=True)
    # Any additional fields or methods you need

    employer = models.ForeignKey(Employer, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.first_name


class Store(models.Model):
    number = models.IntegerField()
    carwash = models.BooleanField(default=False)
    address = models.CharField(max_length=100, null=True)
    address_two = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, null=True)
    province = models.CharField(max_length=100, null=True)
    country = CountryField(null=True)
    phone_number = PhoneNumberField(null=True)
    created = models.DateTimeField(auto_now_add=True, null=True)
    updated = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return f"{self.number}  {self.address}  {self.city}  {self.province}"
