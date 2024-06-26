# Generated by Django 4.2.3 on 2023-07-15 00:10

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0004_customuser_sin"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customuser",
            name="sin",
            field=models.CharField(
                max_length=9,
                null=True,
                validators=[
                    django.core.validators.MinLengthValidator(9),
                    django.core.validators.MaxLengthValidator(9),
                    django.core.validators.RegexValidator(
                        "^\\d{9}$", "SIN number must be 9 digits"
                    ),
                ],
            ),
        ),
    ]
