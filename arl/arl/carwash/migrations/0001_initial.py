# Generated by Django 4.2.10 on 2025-01-27 00:05

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("user", "0028_externalrecipient_is_active"),
    ]

    operations = [
        migrations.CreateModel(
            name="CarwashStatus",
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
                (
                    "status",
                    models.CharField(
                        choices=[("open", "Open"), ("closed", "Closed")], max_length=10
                    ),
                ),
                ("reason", models.TextField(blank=True, null=True)),
                ("date_time", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="carwash_statuses",
                        to="user.store",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
