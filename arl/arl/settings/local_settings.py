import os
import json


try:
    with open('/etc/config.json') as config_file:
        config = json.load(config_file)
except ImportError:
    pass

SECRET_KEY = config.get('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config.get('DEBUG') == 'True'

ALLOWED_HOSTS = ['192.46.223.92']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'dsign',
        'USER': 'postgres',
        'PASSWORD': 'Paulee12!@',
        'HOST': 'localhost'

    }
}
LINODE_ACCESS_KEY = config.get('LINODE_BUCKET_ACCESS_KEY')
LINODE_SECRET_KEY = config.get('LINODE_BUCKET_SECRET_KEY')
LINODE_NAME = config.get('LINODE_BUCKET_NAME')
LINODE_URL = config.get('LINODE_BUCKET_URL')
LINODE_REGION = config.get('LINODE_REGION')
LINODE_BUCKET_NAME = config.get('LINODE_BUCKET_NAME')

DOCUSIGN_INTEGRATION_KEY = config.get('DOCUSIGN_INTEGRATION_KEY')
DOCUSIGN_ACCOUNT_ID = config.get('DOCUSIGN_ACCOUNT_ID')
DOCUSIGN_USER_ID = config.get('DOCUSIGN_USER_ID')
DOCUSIGN_API_CLIENT_HOST = config.get('DOCUSIGN_API_CLIENT_HOST')
DOCUSIGN_OAUTH_HOST_NAME = config.get('DOCUSIGN_OAUTH_HOST_NAME')
DOCUSIGN_BASE_PATH = config.get('DOCUSIGN_BASE_PATH')
DOCUSIGN_TEMPLATE_ID = 'b8ba5457-9257-491a-9729-d6e66bd78a2e'
#DOCUSIGN_PRIVATE_KEY = '/Users/paulfuther/Documents/GitHub/Django-arl/private>

DROP_BOX_SHORT_TOKEN = config.get('DROP_BOX_SHORT_TOKEN')
DROP_BOX_KEY = config.get('DROP_BOX_KEY')
DROP_BOX_SECRET = config.get('DROP_BOX_SECRET')
DROPBOX_REDIRECT_URI = 'https://www.paulfuther.com//dropbox/callback/'
DROP_BOX_REFRESH_TOKEN = config.get('DROP_BOX_REFRESH_TOKEN')
DROP_BOX_AUTHORIZATION_CODE = config.get('DROP_BOX_AUTHORIZATION_CODE')

TWILIO_ACCOUNT_SID = config.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = config.get('TWILIO_AUTH_TOKEN')
TWILIO_FROM = config.get('TWILIO_FROM')
SENDGRID_API_KEY = config.get('SENDGRID_API_KEY')
TWILIO_NOTIFY_SERVICE_SID = config.get('TWILIO_NOTIFY_SERVICE_SID')
TWILIO_ANNOUNCEMENT_SID = config.get('TWILIO_ANNOUNCEMENT_SID')
TWILIO_VERIFY_SID = config.get('TWILIO_VERIFY_SID')
