# Generated by Django 4.2.3 on 2023-11-29 22:17

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0019_alter_customuser_postal"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customuser",
            name="address_two",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
