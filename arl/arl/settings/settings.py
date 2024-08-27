import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
# DEBUG = os.environ.get('DEBUG') == 'True'

DEBUG = True

ALLOWED_HOSTS = ["*"]
ADMINS = [
    ("Paul Futher", "paul.futher@gmail.com"),
    # Add more admins if needed
]

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'django_debug.log'),
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
 }

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "waffle",
    "arl.blog",
    "django_htmx",
    "taggit",
    "arl.user",
    "intl_tel_input",
    "crispy_forms",
    "crispy_bootstrap4",
    "arl.msg",
    "arl.quiz",
    "django_celery_results",
    "django_countries",
    "import_export",
    "flower",
    "django_celery_beat",
    "arl.dsign",
    "arl.dbox",
    "arl.incident",
    "arl.bucket",
    
]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "arl.user.middleware.ErrorLoggingMiddleware",
    "waffle.middleware.WaffleMiddleware",
]

ROOT_URLCONF = "arl.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
            "builtins": ["arl.blog.templatetags.tag_cloud"],
        },
    },
]

WSGI_APPLICATION = "arl.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "dsign",
        "USER": "postgres",
        "PASSWORD": "Paulee12!@",
        "HOST": "localhost",
        'PORT': '5433', 
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "America/New_York"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = "/var/www/static"
# STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATICFILES_DIRS = [BASE_DIR / "static"]

AUTH_USER_MODEL = "user.CustomUser"

CRISPY_TEMPLATE_PACK = "bootstrap4"

CELERY_RESULT_BACKEND = "django-db"


AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_URL = "login/"

BROKER_URL = os.environ.get("CLOUDAMQP_URL")

EMAIL_BACKEND = "arl.msg.helpers.SendGridEmailBackend"

DATA_UPLOAD_MAX_MEMORY_SIZE = 50485760  # 10MB in bytes


DOCUSIGN_BASE_PATH = os.environ.get("DOCUSIGN_BASE_PATH_DEV")
DOCUSIGN_INTEGRATION_KEY = os.environ.get("DOCUSIGN_INTEGRATION_KEY_DEV")
DOCUSIGN_USER_ID = os.environ.get("DOCUSIGN_USER_ID_DEV")
DOCUSIGN_ACCOUNT_ID = os.environ.get("DOCUSIGN_ACCOUNT_ID_DEV")
DOCUSIGN_BASE_PATH = os.environ.get("DOCUSIGN_BASE_PATH_DEV")
DOCUSIGN_API_CLIENT_HOST = os.environ.get("DOCUSIGN_API_CLIENT_HOST_DEV")
DOCUSIGN_TEMPLATE_ID = "e02ea9a2-42d4-453f-bd64-8480b9a2dae4"  # SHORTER TEST DOC
DOCUSIGN_TEMPLATE_ID = "1f4599d9-689a-496d-8a22-24c52529780d"
DOCUSIGN_PRIVATE_KEY = "/Users/paulfuther/Documents/GitHub/Django-arl/privatedev.key"
DOCUSIGN_OAUTH_HOST_NAME = os.environ.get("DOCUSIGN_OAUTH_HOST_NAME_DEV")

# DOCUSIGN_INTEGRATION_KEY = os.environ.get("DOCUSIGN_INTEGRATION_KEY")
# NEW_HIRE_DATA_EMAIL = ["paul.futher@gmail.com", "hr1553690@yahoo.com"]
# DOCUSIGN_ACCOUNT_ID = os.environ.get("DOCUSIGN_ACCOUNT_ID")
# DOCUSIGN_USER_ID = os.environ.get("DOCUSIGN_USER_ID")
# DOCUSIGN_API_CLIENT_HOST = os.environ.get("DOCUSIGN_API_CLIENT_HOST")
# DOCUSIGN_OAUTH_HOST_NAME = os.environ.get("DOCUSIGN_OAUTH_HOST_NAME")
# DOCUSIGN_BASE_PATH = os.environ.get("DOCUSIGN_BASE_PATH")
# DOCUSIGN_TEST_TEMPLATE_ID = "f34f7bd5-c31a-44ae-941c-d16b8ec809c8"
# DOCUSIGN_TEMPLATE_ID = "b8ba5457-9257-491a-9729-d6e66bd78a2e"
# DOCUSIGN_PRIVATE_KEY = "/Users/paulfuther/Documents/GitHub/Django-arl/private.key"


DROP_BOX_SHORT_TOKEN = os.environ.get("DROP_BOX_SHORT_TOKEN")
DROP_BOX_KEY = os.environ.get("DROP_BOX_KEY")
DROP_BOX_SECRET = os.environ.get("DROP_BOX_SECRET")
DROPBOX_REDIRECT_URI = "http://localhost:8000/dropbox/callback/"
DROP_BOX_REFRESH_TOKEN = os.environ.get("DROP_BOX_REFRESH_TOKEN")
DROP_BOX_AUTHORIZATION_CODE = os.environ.get("DROP_BOX_AUTHORIZATION_CODE")

LINODE_ACCESS_KEY = os.environ.get("LINODE_BUCKET_ACCESS_KEY")
LINODE_SECRET_KEY = os.environ.get("LINODE_BUCKET_SECRET_KEY")
LINODE_NAME = os.environ.get("LINODE_BUCKET_NAME")
LINODE_URL = os.environ.get("LINODE_BUCKET_URL")
LINODE_REGION = os.environ.get("LINODE_REGION")
LINODE_BUCKET_NAME = os.environ.get("LINODE_BUCKET_NAME")
LINODE_S3_POSTGRES_FOLDER = os.environ.get("LINODE_S3_POSTGRES_FOLDER")

# twillio variables

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.environ.get("TWILIO_FROM")
TWILIO_VERIFY_SID = os.environ.get("TWILIO_VERIFY_SID")
TWILIO_NOTIFY_SERVICE_SID = os.environ.get("TWILIO_NOTIFY_SERVICE_SID")
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER")
SENDGRID_NEWHIRE_ID = os.environ.get("SENDGRID_NEWHIRE_ID")
SENDGRID_NEW_HIRE_FILE_ID = os.environ.get("SENDGRID_NEW_HIRE_FILE_ID")

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = "smtp.sendgrid.net"
EMAIL_HOST_USER = "apikey"  # this is exactly the value 'apikey'
EMAIL_HOST_PASSWORD = SENDGRID_API_KEY
EMAIL_PORT = 587
EMAIL_USE_TLS = True


BACKUP_FILE_PATH = os.environ.get("BACKUP_FILE_PATH_DEV")
BACKUP_DUMP_PATH = os.environ.get("BACKUP_DUMP_PATH_DEV")


try:
    from .local_settings import *
except ImportError:
    pass
