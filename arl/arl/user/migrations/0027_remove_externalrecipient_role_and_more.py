# Generated by Django 4.2.10 on 2024-08-27 01:31

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("user", "0026_role_externalrecipient"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="externalrecipient",
            name="role",
        ),
        migrations.AddField(
            model_name="externalrecipient",
            name="group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="auth.group",
            ),
        ),
        migrations.DeleteModel(
            name="Role",
        ),
    ]
