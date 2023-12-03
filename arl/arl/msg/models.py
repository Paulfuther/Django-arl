from django.db import models

from arl.user.models import CustomUser


class Twimlmessages(models.Model):
    twimlname = models.CharField(max_length=100)
    twimlid = models.CharField(max_length=100)

    def __str__(self):
        return '%r' % (self.twimlname)


class BulkEmailSendgrid(models.Model):
    templatename = models.CharField(max_length=100)
    templateid = models.CharField(max_length=100)

    def __str__(self):
        return '%r' % (self.templatename)


class EmailEvent(models.Model):
    EVENT_CHOICES = (
        ('click', 'Click'),
        ('delivered', 'Delivered'),
        ('open', 'Open'),
    )
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    username = models.CharField(max_length=150, default='unknown')
    email = models.EmailField()
    event = models.CharField(max_length=10, choices=EVENT_CHOICES)
    ip = models.GenericIPAddressField()
    sg_event_id = models.CharField(max_length=255)
    sg_message_id = models.CharField(max_length=255)
    sg_template_id = models.CharField(max_length=255)
    sg_template_name = models.CharField(max_length=255)
    timestamp = models.DateTimeField()
    url = models.URLField()
    useragent = models.TextField()

    def __str__(self):
        return f'{self.email} - {self.event}'

    class Meta:
        ordering = ['-timestamp']


class SmsLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    level = models.CharField(max_length=10)
    message = models.TextField()

    def __str__(self):
        return f"{self.timestamp} - {self.level}: {self.message}"
    
    
class EmailTemplate(models.Model):
    name = models.CharField(max_length=100, null=True)
    sendgrid_id = models.TextField()

    def __str__(self):
        return self.name