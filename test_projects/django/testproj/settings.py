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
BROKER_URL = 'memory://'
BROKER_CONNECTION_TIMEOUT = 1
BROKER_CONNECTION_RETRY = False
BROKER_CONNECTION_MAX_RETRIES = 1
# The default BROKER_POOL_LIMIT is 10, broker connections are not
# properly cleaned up on error, so the tests will run out of
# connections and result in one test hanging forever
# To prevent that, just disable it
BROKER_POOL_LIMIT = 0
CELERY_RESULT_BACKEND = 'cache'
from celery import VERSION
if VERSION[0] < 3:
    # Use Django's syntax instead of Celery's, which would be:
    CELERY_CACHE_BACKEND = 'locmem://'
else:
    CELERY_CACHE_BACKEND = 'memory'

CELERY_SEND_TASK_ERROR_EMAILS = False

import djcelery
djcelery.setup_loader()
