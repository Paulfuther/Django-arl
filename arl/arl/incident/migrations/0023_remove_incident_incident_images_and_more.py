# Generated by Django 4.2.3 on 2023-08-20 22:47

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("incident", "0022_incident_image_folder_incident_incident_images"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="incident",
            name="incident_images",
        ),
        migrations.DeleteModel(
            name="Incident_Files",
        ),
    ]
