# Generated by Django 4.2.10 on 2024-04-21 19:25

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("msg", "0013_userconsent"),
    ]

    operations = [
        migrations.CreateModel(
            name="WhatsAppMessage",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("sender", models.CharField(max_length=20)),
                ("receiver", models.CharField(max_length=20)),
                ("message_status", models.CharField(max_length=10)),
                ("username", models.CharField(blank=True, max_length=100, null=True)),
            ],
        ),
    ]