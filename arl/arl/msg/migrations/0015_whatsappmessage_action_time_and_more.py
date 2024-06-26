# Generated by Django 4.2.10 on 2024-04-21 19:37

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("msg", "0014_whatsappmessage"),
    ]

    operations = [
        migrations.AddField(
            model_name="whatsappmessage",
            name="action_time",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name="whatsappmessage",
            name="template_used",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="whatsappmessage",
            name="message_status",
            field=models.CharField(max_length=20),
        ),
    ]
