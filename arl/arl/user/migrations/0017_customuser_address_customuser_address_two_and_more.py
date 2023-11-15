# Generated by Django 4.2.3 on 2023-11-12 20:15

import django.core.validators
from django.db import migrations, models
import django_countries.fields


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0016_customuser_dob"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="address",
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="customuser",
            name="address_two",
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="customuser",
            name="city",
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="customuser",
            name="country",
            field=django_countries.fields.CountryField(max_length=2, null=True),
        ),
        migrations.AddField(
            model_name="customuser",
            name="postal",
            field=models.CharField(
                blank=True,
                max_length=7,
                null=True,
                validators=[
                    django.core.validators.RegexValidator(
                        message="Enter a valid postal code format (e.g., 123-4567).",
                        regex="^\\d{3}-\\d{4}$",
                    )
                ],
            ),
        ),
        migrations.AddField(
            model_name="customuser",
            name="state_province",
            field=models.CharField(max_length=100, null=True),
        ),
    ]