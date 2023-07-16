from django.db import models


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
