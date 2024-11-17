# Generated by Django 4.2.10 on 2024-11-10 15:34

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("msg", "0016_message_delete_whatsappmessage"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailList",
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
                ("email", models.EmailField(max_length=254, unique=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
        ),
    ]
