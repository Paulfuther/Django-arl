# Generated by Django 4.2.3 on 2023-08-16 23:50

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("incident", "0012_alter_incident_correctiveactions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="incident",
            name="actionstaken",
            field=models.CharField(default=""),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="incident",
            name="correctiveactions",
            field=models.CharField(),
        ),
    ]
