from django.db import models
from arl.user.models import Employer


class Incident(models.Model):
    employer = models.ForeignKey(Employer, on_delete=models.SET_NULL, null=True)

    injuryorillness = models.BooleanField(default=False)
    environmental = models.BooleanField(default=False)
    regulatory = models.BooleanField(default=False)
    economicdamage = models.BooleanField(default=False)
    reputation = models.BooleanField(default=False)
    security = models.BooleanField(default=False)
    fire = models.BooleanField(default=False)

    suncoremployee = models.BooleanField(default=False)
    contractor = models.BooleanField(default=False)
    associate = models.BooleanField(default=False)
    generalpublic = models.BooleanField(default=False)
    other = models.BooleanField(default=False)
    othertext = models.CharField(max_length=255)

    def __str__(self):
        return f"Incident {self.id}"
