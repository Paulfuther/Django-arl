from __future__ import absolute_import, unicode_literals

import os


from celery import Celery
from django.conf import settings


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'arl.settings.base')

app = Celery('arl')

app.config_from_object(settings, namespace='CELERY')
app.conf.broker_url = settings.BROKER_URL
app.autodiscover_tasks(['arl'])
