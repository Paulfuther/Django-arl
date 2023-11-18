# Generated by Django 4.2.3 on 2023-11-18 22:50

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("msg", "0007_rename_name_emailtemplate_sendgrid_id"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="emailtemplate",
            name="content",
        ),
        migrations.AddField(
            model_name="emailtemplate",
            name="name",
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name="emailtemplate",
            name="sendgrid_id",
            field=models.TextField(),
        ),
    ]
