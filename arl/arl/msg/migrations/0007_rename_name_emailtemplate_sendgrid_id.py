# Generated by Django 4.2.3 on 2023-11-18 22:47

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("msg", "0006_emailtemplate"),
    ]

    operations = [
        migrations.RenameField(
            model_name="emailtemplate",
            old_name="name",
            new_name="sendgrid_id",
        ),
    ]
