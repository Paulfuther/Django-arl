from django.contrib.auth.models import AbstractUser, Group
from django.core.validators import (
    MaxLengthValidator,
    MinLengthValidator,
    RegexValidator,
)
from django.db import models
from django_countries.fields import CountryField
from phonenumber_field.modelfields import PhoneNumberField


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

    employer = models.ForeignKey(
        Employer, on_delete=models.CASCADE, null=True, related_name="stores"
    )
    manager = models.ForeignKey('CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_stores')

    def __str__(self):
        if self.employer:
            manager_name = self.manager.first_name if self.manager else "No Manager"
            return f"Store {self.number} - {self.address} - Manager: {manager_name}"
        else:
            return f"Store {self.number}"


class CustomUser(AbstractUser):
    phone_number = models.CharField(max_length=20)
    sin = models.CharField(
        max_length=9,
        validators=[
            MinLengthValidator(9),
            MaxLengthValidator(9),
            RegexValidator(r"^\d{9}$", "SIN number must be 9 digits"),
        ],
        null=True,
    )
    dob = models.DateField(blank=True, null=True, verbose_name="Date of Birth")
    address = models.CharField(max_length=100, null=True)
    address_two = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True)
    state_province = models.CharField(max_length=100, null=True)
    country = CountryField(null=True)
    postal = models.CharField(max_length=7, null=True)
    store = models.ForeignKey(Store, on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    employer = models.ForeignKey(Employer, on_delete=models.SET_NULL, null=True)
    store = models.ForeignKey(Store, on_delete=models.SET_NULL, null=True, blank=True, related_name='users')

    def __str__(self):
        return self.first_name

    @property
    def is_docusign(self):
        return self.groups.filter(name="docusign").exists()

    @property
    def is_dropbox(self):
        return self.groups.filter(name="dropbox").exists()

    @property
    def is_incident_form(self):
        return self.groups.filter(name="incident_form").exists()

    @property
    def is_comms(self):
        return self.groups.filter(name="comms").exists()

    @property
    def is_template_email(self):
        return self.groups.filter(name="template_email").exists()

    @property
    def is_storage(self):
        return self.groups.filter(name="storage").exists()


class UserManager(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE,
                                related_name='user_manager_profile')
    manager = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="managed_users"
    )

    def __str__(self):
        return self.user.username


class ErrorLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    path = models.CharField(max_length=255)
    method = models.CharField(max_length=10)
    status_code = models.IntegerField()
    error_message = models.TextField()


class ExternalRecipient(models.Model):
    first_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50, blank=True, null=True)
    company = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(unique=True)
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.email}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()