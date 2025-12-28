from django.db import models


class HelpCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Help Categories"

    def __str__(self):
        return self.name


class HelpSection(models.Model):
    category = models.ForeignKey(
        "HelpCategory", on_delete=models.CASCADE, related_name="sections", null=True
    )
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title
