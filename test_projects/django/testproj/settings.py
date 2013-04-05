import os
import warnings

# Ignore deprecation warnings caused by running the same project with different
# versions of Django
warnings.filterwarnings(
    'ignore',
    category=DeprecationWarning,
    module=r'django\.core\.management',
)
warnings.filterwarnings(
    'ignore',
    category=DeprecationWarning,
    module=r'django_nose\.management\.commands\.test',
)

here = os.path.abspath(os.path.dirname(__file__))

ROOT_URLCONF = 'testproj.urls'

DEBUG = True
TEMPLATE_DEBUG = DEBUG
USE_TZ = True
TIME_ZONE = 'UTC'
SITE_ID = 1
SECRET_KEY = ')&a$!r0n!&c$$!-!%r)4kq4b5y9jncx(&2ulmb2*nvx^yi^bp5'
ADMINS = ()
MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(here, 'jobtastic-test-db'),
        'USER': '',
        'PASSWORD': '',
        'PORT': '',
    }
}

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'djcelery',
    'testproj.someapp',
    'jobtastic',
    'django_nose',
)


NOSE_ARGS = [
    os.path.join(here, os.pardir, os.pardir, os.pardir, 'jobtastic', 'tests'),
    os.environ.get("NOSE_VERBOSE") and "--verbose" or "",
]
TEST_RUNNER = 'django_nose.run_tests'

# Celery Configuration

BROKER_HOST = "localhost"
BROKER_PORT = 5672
BROKER_VHOST = "/"
BROKER_USER = "guest"
BROKER_PASSWORD = "guest"

TT_HOST = "localhost"
TT_PORT = 1978

CELERY_DEFAULT_EXCHANGE = "testcelery"
CELERY_DEFAULT_ROUTING_KEY = "testcelery"
CELERY_DEFAULT_QUEUE = "testcelery"

CELERY_QUEUES = {
    "testcelery": {
        "binding_key": "testcelery",
    },
}
CELERY_SEND_TASK_ERROR_EMAILS = False

import djcelery
djcelery.setup_loader()
