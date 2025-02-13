# Generated by Django 4.2.10 on 2025-02-12 19:06

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("incident", "0037_incident_do_not_send"),
    ]

    operations = [
        migrations.AddField(
            model_name="incident",
            name="causalfactors",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="incident",
            name="determincauses",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="incident",
            name="preventiveactions",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="incident",
            name="shared_learning_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="incident",
            name="shared_learning_method",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="incident",
            name="shared_learning_na",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="incident",
            name="shared_learning_no",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="incident",
            name="shared_learning_yes",
            field=models.BooleanField(default=False),
        ),
    ]
