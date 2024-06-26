# Generated by Django 4.2.3 on 2023-08-12 23:25

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("incident", "0005_remove_incident_rna_remove_incident_rno_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="incident",
            name="air",
        ),
        migrations.RemoveField(
            model_name="incident",
            name="chemcomment",
        ),
        migrations.RemoveField(
            model_name="incident",
            name="chemical",
        ),
        migrations.RemoveField(
            model_name="incident",
            name="deiselexhaustfluid",
        ),
        migrations.RemoveField(
            model_name="incident",
            name="diesel",
        ),
        migrations.RemoveField(
            model_name="incident",
            name="gas",
        ),
        migrations.RemoveField(
            model_name="incident",
            name="land",
        ),
        migrations.RemoveField(
            model_name="incident",
            name="sewage",
        ),
        migrations.RemoveField(
            model_name="incident",
            name="sother",
        ),
        migrations.RemoveField(
            model_name="incident",
            name="water",
        ),
        migrations.RemoveField(
            model_name="incident",
            name="wildlife",
        ),
        migrations.AddField(
            model_name="incident",
            name="product_that_was_spilled",
            field=models.CharField(
                blank=True,
                choices=[
                    ("Gas", "Gas"),
                    ("Diesel", "Diesel"),
                    ("Sewage", "Sewage"),
                    ("Chemical", "Chemical"),
                    ("Diesel Exhaust Fluid", "Diesel Exhaust Fluid"),
                    ("Other", "Other"),
                ],
                max_length=25,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="incident",
            name="source_impacted",
            field=models.CharField(
                blank=True,
                choices=[
                    ("Air", "Air"),
                    ("Water", "Water"),
                    ("Wildlife", "Wildlife"),
                    ("Land", "Land"),
                ],
                max_length=25,
                null=True,
            ),
        ),
    ]
