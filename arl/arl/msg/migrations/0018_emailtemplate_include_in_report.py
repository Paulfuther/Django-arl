# Generated by Django 4.2.10 on 2025-01-09 23:16

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("msg", "0017_emaillist"),
    ]

    operations = [
        migrations.AddField(
            model_name="emailtemplate",
            name="include_in_report",
            field=models.BooleanField(default=False),
        ),
    ]
