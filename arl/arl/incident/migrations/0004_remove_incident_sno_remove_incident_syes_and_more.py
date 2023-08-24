# Generated by Django 4.2.3 on 2023-08-12 22:59

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("incident", "0003_alter_incident_brief_description"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="incident",
            name="sno",
        ),
        migrations.RemoveField(
            model_name="incident",
            name="syes",
        ),
        migrations.AddField(
            model_name="incident",
            name="product_spilled",
            field=models.CharField(
                blank=True, choices=[("Y", "Yes"), ("N", "No")], max_length=1, null=True
            ),
        ),
    ]