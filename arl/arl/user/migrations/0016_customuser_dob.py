# Generated by Django 4.2.3 on 2023-11-12 19:41

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0015_alter_store_employer"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="dob",
            field=models.DateField(blank=True, null=True, verbose_name="Date of Birth"),
        ),
    ]
