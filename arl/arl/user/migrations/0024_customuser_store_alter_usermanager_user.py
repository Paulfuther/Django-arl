# Generated by Django 4.2.10 on 2024-06-11 18:17

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0023_usermanager"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="store",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="users",
                to="user.store",
            ),
        ),
        migrations.AlterField(
            model_name="usermanager",
            name="user",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="user_manager_profile",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
