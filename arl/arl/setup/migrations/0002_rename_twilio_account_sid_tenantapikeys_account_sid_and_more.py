# Generated by Django 4.2.10 on 2025-02-15 19:34

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0033_employer_verified_sender_email"),
        ("setup", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="tenantapikeys",
            old_name="twilio_account_sid",
            new_name="account_sid",
        ),
        migrations.RenameField(
            model_name="tenantapikeys",
            old_name="dropbox_access_token",
            new_name="api_key",
        ),
        migrations.RenameField(
            model_name="tenantapikeys",
            old_name="twilio_auth_token",
            new_name="auth_token",
        ),
        migrations.RemoveField(
            model_name="tenantapikeys",
            name="sendgrid_api_key",
        ),
        migrations.RemoveField(
            model_name="tenantapikeys",
            name="twilio_service_sid",
        ),
        migrations.RemoveField(
            model_name="tenantapikeys",
            name="updated_at",
        ),
        migrations.AddField(
            model_name="tenantapikeys",
            name="service_name",
            field=models.CharField(
                choices=[("twilio", "Twilio"), ("dropbox", "Dropbox")],
                default="",
                max_length=50,
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="tenantapikeys",
            name="employer",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="api_keys",
                to="user.employer",
            ),
        ),
    ]
