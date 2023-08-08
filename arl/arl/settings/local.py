import os
from pathlib import Path

from dotenv import load_dotenv

from .base import *

load_dotenv()
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

DOCUSIGN_BASE_PATH = os.environ.get('DOCUSIGN_BASE_PATH_DEV')
DOCUSIGN_INTEGRATION_KEY = os.environ.get('DOCUSIGN_INTEGRATION_KEY_DEV')
DOCUSIGN_USER_ID = os.environ.get('DOCUSIGN_USER_ID_DEV')
DOCUSIGN_ACCOUNT_ID = os.environ.get('DOCUSIGN_ACCOUNT_ID_DEV')
DOCUSIGN_BASE_PATH = os.environ.get('DOCUSIGN_BASE_PATH_DEV')
DOCUSIGN_API_CLIENT_HOST = os.environ.get('DOCUSIGN_API_CLIENT_HOST_DEV')
DOCUSIGN_TEMPLATE_ID = '1f4599d9-689a-496d-8a22-24c52529780d'
DOCUSIGN_PRIVATE_KEY = '/Users/paulfuther/Documents/GitHub/Django-arl/privatedev.key'
DOCUSIGN_OAUTH_HOST_NAME = os.environ.get('DOCUSIGN_OAUTH_HOST_NAME_DEV')


DROP_BOX_SHORT_TOKEN = os.environ.get('DROP_BOX_SHORT_TOKEN')
DROP_BOX_KEY = os.environ.get('DROP_BOX_KEY')
DROP_BOX_SECRET = os.environ.get('DROP_BOX_SECRET')
DROPBOX_REDIRECT_URI = 'http://localhost:8000/dropbox/callback/'
DROP_BOX_REFRESH_TOKEN = os.environ.get('DROP_BOX_REFRESH_TOKEN')
