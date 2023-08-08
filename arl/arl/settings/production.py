import os
from pathlib import Path

from dotenv import load_dotenv

from .base import *

DOCUSIGN_INTEGRATION_KEY = os.environ.get('DOCUSIGN_INTEGRATION_KEY')
NEW_HIRE_DATA_EMAIL = ['paul.futher@gmail.com', 'hr1553690@yahoo.com']
DOCUSIGN_ACCOUNT_ID = os.environ.get('DOCUSIGN_ACCOUNT_ID')
DOCUSIGN_USER_ID = os.environ.get('DOCUSIGN_USER_ID')
DOCUSIGN_API_CLIENT_HOST = os.environ.get('DOCUSIGN_API_CLIENT_HOST')
DOCUSIGN_OAUTH_HOST_NAME = os.environ.get('DOCUSIGN_OAUTH_HOST_NAME')
DOCUSIGN_BASE_PATH = os.environ.get('DOCUSIGN_BASE_PATH')
DOCUSIGN_TEMPLATE_ID = 'b8ba5457-9257-491a-9729-d6e66bd78a2e'
DOCUSIGN_PRIVATE_KEY = '/Users/paulfuther/Documents/GitHub/Django-arl/private.key'

DROP_BOX_SHORT_TOKEN = os.environ.get('DROP_BOX_SHORT_TOKEN')
DROP_BOX_KEY = os.environ.get('DROP_BOX_KEY')
DROP_BOX_SECRET = os.environ.get('DROP_BOX_SECRET')
DROPBOX_REDIRECT_URI = 'http://localhost:8000/dropbox/callback/'
DROP_BOX_REFRESH_TOKEN = os.environ.get('DROP_BOX_REFRESH_TOKEN')
