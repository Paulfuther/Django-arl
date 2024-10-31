# Generated by Django 4.2.10 on 2024-10-30 22:16

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("quiz", "0007_saltlog_user_employer"),
    ]

    operations = [
        migrations.AddField(
            model_name="saltlog",
            name="user",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="salt_log",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
