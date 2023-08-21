# Generated by Django 4.2.3 on 2023-08-12 23:01

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("incident", "0004_remove_incident_sno_remove_incident_syes_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="incident",
            name="rna",
        ),
        migrations.RemoveField(
            model_name="incident",
            name="rno",
        ),
        migrations.RemoveField(
            model_name="incident",
            name="ryes",
        ),
        migrations.AddField(
            model_name="incident",
            name="regulatory_authorities_notified",
            field=models.CharField(
                blank=True, choices=[("Y", "Yes"), ("N", "No")], max_length=1, null=True
            ),
        ),
    ]
