from __future__ import print_function
import mock
import django
from unittest import skipIf
from celery import Celery, states
from celery.backends.cache import DummyClient
from django.conf import settings
from django.test import TestCase
from jobtastic.task import JobtasticTask
from werkzeug.contrib.cache import MemcachedCache
try:
    from django.core.cache import caches
except ImportError:
    pass


def add(self, key, value, timeout=None):
    """
    Fake atomic add method for memcache clients
    """
    self.set(key, value, timeout)
    return True


@skipIf(django.VERSION < (1, 7),
        "Django < 1.7 doesn't support django.core.cache.caches")
class DjangoSettingsTestCase(TestCase):

    def setUp(self):

        # Define the class in setup so it has the same cache
        # scope as the test
        class ParrotTask(JobtasticTask):
            """
            Just return whatever is passed in as the result.
            """
            significant_kwargs = [
                ('result', str),
            ]
            herd_avoidance_timeout = 0

            def calculate_result(self, result, **kwargs):
                return result

        self.task = ParrotTask
        self.kwargs = {'result': 42}
        self.key = self.task._get_cache_key(**self.kwargs)

    def test_sanity(self):
        # The task actually runs
        with self.settings(CELERY_ALWAYS_EAGER=True):
            async_task = self.task.delay(result=1)
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 1)

    def test_default_django_cache(self):
        with self.settings(CELERY_ALWAYS_EAGER=False):
            app = Celery()
            app.config_from_object(settings)
            self.task.bind(app)
            app.finalize()
            async_task = self.task.delay(**self.kwargs)
            self.assertEqual(async_task.status, states.PENDING)
            self.assertTrue('herd:%s' % self.key in caches['default'])

    def test_custom_django_cache(self):
        with self.settings(
            CELERY_ALWAYS_EAGER=False,
            JOBTASTIC_CACHE='shared',
            CACHES={'default':
                    {'BACKEND':
                     'django.core.cache.backends.locmem.LocMemCache',
                     'LOCATION': 'default'},
                    'shared':
                    {'BACKEND':
                     'django.core.cache.backends.locmem.LocMemCache',
                     'LOCATION': 'shared'}}):
            app = Celery()
            app.config_from_object(settings)
            self.task.bind(app)
            app.finalize()
            async_task = self.task.delay(**self.kwargs)
            self.assertEqual(async_task.status, states.PENDING)
            self.assertTrue('herd:%s' % self.key in caches['shared'])
            self.assertTrue('herd:%s' % self.key not in caches['default'])

    @mock.patch('jobtastic.cache.CACHES', ['Werkzeug'])
    @mock.patch.object(DummyClient, 'add', add, create=True)
    def test_default_werkzeug_cache(self):
        with self.settings(CELERY_ALWAYS_EAGER=False):
            app = Celery()
            app.config_from_object(settings)
            self.task.bind(app)
            app.finalize()
            async_task = self.task.delay(**self.kwargs)
            cache = MemcachedCache(app.backend.client)
            self.assertEqual(async_task.status, states.PENDING)
            self.assertNotEqual(cache.get('herd:%s' % self.key), None)
