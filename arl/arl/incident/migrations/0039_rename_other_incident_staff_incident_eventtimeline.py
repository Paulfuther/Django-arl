# Generated by Django 4.2.10 on 2025-02-12 19:31

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("incident", "0038_incident_causalfactors_incident_determincauses_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="incident",
            old_name="other",
            new_name="staff",
        ),
        migrations.AddField(
            model_name="incident",
            name="eventtimeline",
            field=models.TextField(default=""),
        ),
    ]
