from django.db import models

# Create your models here.

class DocuSignTemplate(models.Model):
    template_id = models.CharField(max_length=100, unique=True)
    template_name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.template_name} (ID: {self.template_id})"