from django.db import models


class HelpSection(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title
