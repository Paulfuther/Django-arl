# Generated by Django 4.2.20 on 2025-04-27 17:52

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dsign", "0018_processeddocsigndocument_is_company_document"),
    ]

    operations = [
        migrations.AddField(
            model_name="signeddocumentfile",
            name="is_company_document",
            field=models.BooleanField(default=False),
        ),
    ]
