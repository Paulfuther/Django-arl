# Generated by Django 4.2.10 on 2025-03-22 20:15

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("user", "0052_alter_newhireinvite_role"),
        ("dsign", "0011_processeddocsigndocument_employer"),
    ]

    operations = [
        migrations.CreateModel(
            name="SignedDocumentFile",
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
                ("envelope_id", models.CharField(max_length=255)),
                ("file_name", models.CharField(max_length=255)),
                ("file_path", models.CharField(max_length=512)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "employer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="user.employer"
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="signed_documents",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
