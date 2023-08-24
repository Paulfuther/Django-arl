# Generated by Django 4.2.3 on 2023-08-12 21:58

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("user", "0014_store_employer"),
    ]

    operations = [
        migrations.CreateModel(
            name="Incident",
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
                ("injuryorillness", models.BooleanField(default=False)),
                ("environmental", models.BooleanField(default=False)),
                ("regulatory", models.BooleanField(default=False)),
                ("economicdamage", models.BooleanField(default=False)),
                ("reputation", models.BooleanField(default=False)),
                ("security", models.BooleanField(default=False)),
                ("fire", models.BooleanField(default=False)),
                ("eventdetails", models.TextField()),
                ("eventdate", models.DateField(null=True)),
                ("eventtime", models.TimeField(null=True)),
                ("reportedby", models.CharField(max_length=255)),
                ("reportedbynumber", models.CharField(max_length=255)),
                ("suncoremployee", models.BooleanField(default=False)),
                ("contractor", models.BooleanField(default=False)),
                ("associate", models.BooleanField(default=False)),
                ("generalpublic", models.BooleanField(default=False)),
                ("other", models.BooleanField(default=False)),
                ("othertext", models.CharField(max_length=255)),
                ("actionstaken", models.TextField()),
                ("correctiveactions", models.TextField()),
                ("sno", models.BooleanField(default=False)),
                ("syes", models.BooleanField(default=False)),
                ("scomment", models.CharField(max_length=255)),
                ("rna", models.BooleanField(default=False)),
                ("rno", models.BooleanField(default=False)),
                ("ryes", models.BooleanField(default=False)),
                ("rcomment", models.CharField(max_length=255)),
                ("gas", models.BooleanField(default=False)),
                ("diesel", models.BooleanField(default=False)),
                ("sewage", models.BooleanField(default=False)),
                ("chemical", models.BooleanField(default=False)),
                ("chemcomment", models.CharField(max_length=255)),
                ("deiselexhaustfluid", models.BooleanField(default=False)),
                ("sother", models.BooleanField(default=False)),
                ("s2comment", models.CharField(max_length=255)),
                ("air", models.BooleanField(default=False)),
                ("water", models.BooleanField(default=False)),
                ("wildlife", models.BooleanField(default=False)),
                ("land", models.BooleanField(default=False)),
                ("volumerelease", models.CharField(max_length=255)),
                ("pyes", models.BooleanField(default=False)),
                ("pno", models.BooleanField(default=False)),
                ("pna", models.BooleanField(default=False)),
                ("pcase", models.CharField(max_length=255)),
                ("stolentransactions", models.BooleanField(default=False)),
                ("stoltransactions", models.CharField(max_length=255)),
                ("stolencards", models.BooleanField(default=False)),
                ("stolcards", models.CharField(max_length=255)),
                ("stolentobacco", models.BooleanField(default=False)),
                ("stoltobacco", models.CharField(max_length=255)),
                ("stolenlottery", models.BooleanField(default=False)),
                ("stollottery", models.CharField(max_length=255)),
                ("stolenfuel", models.BooleanField(default=False)),
                ("stolfuel", models.CharField(max_length=255)),
                ("stolenother", models.BooleanField(default=False)),
                ("stolother", models.CharField(max_length=255)),
                ("stolenothervalue", models.CharField(max_length=255)),
                ("stolenna", models.BooleanField(default=False)),
                ("gender", models.CharField(max_length=255)),
                ("height", models.CharField(max_length=255)),
                ("weight", models.CharField(max_length=255)),
                ("haircolor", models.CharField(max_length=255)),
                ("haircut", models.CharField(max_length=255)),
                ("complexion", models.CharField(max_length=255)),
                ("beardmoustache", models.CharField(max_length=255)),
                ("eyeeyeglasses", models.CharField(max_length=255)),
                ("licencenumber", models.CharField(max_length=255)),
                ("makemodel", models.CharField(max_length=255)),
                ("color", models.CharField(max_length=255)),
                ("scars", models.CharField(max_length=255)),
                ("tatoos", models.CharField(max_length=255)),
                ("hat", models.CharField(max_length=255)),
                ("shirt", models.CharField(max_length=255)),
                ("trousers", models.CharField(max_length=255)),
                ("shoes", models.CharField(max_length=255)),
                ("voice", models.CharField(max_length=255)),
                ("bumpersticker", models.CharField(max_length=255)),
                ("direction", models.CharField(max_length=255)),
                ("damage", models.CharField(max_length=255)),
                ("image_folder", models.CharField(max_length=255)),
                (
                    "employer",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="user.employer",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Incident_Files",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("image", models.FileField(upload_to="incident_images/")),
                (
                    "incident",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="incident.incident",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="incident",
            name="incident_images",
            field=models.ManyToManyField(
                related_name="incident_images", to="incident.incident_files"
            ),
        ),
        migrations.AddField(
            model_name="incident",
            name="store",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="incidents",
                to="user.store",
            ),
        ),
    ]