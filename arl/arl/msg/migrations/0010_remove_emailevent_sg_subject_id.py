# Generated by Django 4.2.3 on 2024-01-09 18:51

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("msg", "0009_emailevent_sg_subject_id_alter_emailevent_event"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="emailevent",
            name="sg_subject_id",
        ),
    ]
