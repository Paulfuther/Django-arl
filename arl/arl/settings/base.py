import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG') == 'True'

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'arl.blog',
    'django_htmx',
    'taggit',
    'arl.user',
    'intl_tel_input',
    'crispy_forms',
    'crispy_bootstrap4',
    'arl.msg',
    'django_celery_results',
    'django_countries',
    'import_export',
    'flower',
    'django_celery_beat',
    'arl.dsign',
    'arl.dbox',
    'arl.incident'
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = 'arl.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, "templates")],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
            "builtins":[
                "arl.blog.templatetags.tag_cloud"
            ],
        },
    },
]

WSGI_APPLICATION = 'arl.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'dsign',
        'USER': 'postgres',
        'PASSWORD': 'Paulee12!@',
        'HOST': 'localhost'

    }
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

STATICFILES_DIRS = [BASE_DIR / "static"]

AUTH_USER_MODEL = 'user.CustomUser'

CRISPY_TEMPLATE_PACK = 'bootstrap4'

BROKER_URL = os.environ.get('CLOUDAMQP_URL')

CELERY_RESULT_BACKEND = 'django-db'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

LOGIN_URL = 'login',

LINODE_ACCESS_KEY = os.environ.get('LINODE_BUCKET_ACCESS_KEY')
LINODE_SECRET_KEY = os.environ.get('LINODE_BUCKET_SECRET_KEY')
LINODE_NAME = os.environ.get('LINODE_BUCKET_NAME')
LINODE_URL = os.environ.get('LINODE_BUCKET_URL')
LINODE_REGION = os.environ.get('LINODE_REGION')
LINODE_BUCKET_NAME = os.environ.get('LINODE_BUCKET_NAME')

try:
    from .local_settings import *
except ImportError:
    pass