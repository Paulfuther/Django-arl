# Generated by Django 4.2.3 on 2023-08-16 23:43

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("incident", "0011_alter_incident_actionstaken"),
    ]

    operations = [
        migrations.AlterField(
            model_name="incident",
            name="correctiveactions",
            field=models.TextField(null=True),
        ),
    ]
