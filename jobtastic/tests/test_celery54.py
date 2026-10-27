# coding: utf-8

from contextlib import contextmanager
from unittest import TestCase
from unittest.mock import patch

from celery import Celery
from celery import Task
from celery.states import FAILURE
from celery.states import PENDING
from celery.states import SUCCESS
from kombu.exceptions import OperationalError

from django.conf import settings
from django.core.cache import caches
from django.core.cache.backends.base import InvalidCacheBackendError

from jobtastic import JobtasticTask
from jobtastic.cache import get_cache
from jobtastic.cache.base import BaseCache
from jobtastic.states import PROGRESS


if not settings.configured:
    settings.configure(
        CACHES={
            'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
            'shared': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                'LOCATION': 'jobtastic-shared',
            },
        },
    )


class MemoryCache(BaseCache):
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, timeout=None):
        self.values[key] = value

    def delete(self, key):
        self.values.pop(key, None)

    @contextmanager
    def lock(self, lock_name, timeout=900):
        yield


class ParrotTask(JobtasticTask):
    name = 'jobtastic.tests.ParrotTask'
    significant_kwargs = [('result', str)]
    herd_avoidance_timeout = 60

    def calculate_result(self, result):
        return result


class TestCelery54(TestCase):
    def setUp(self):
        self.app = Celery('jobtastic-test', set_as_current=False)
        self.app.conf.update(
            broker_url='memory://',
            result_backend='cache+memory://',
            task_always_eager=True,
        )
        self.addCleanup(self.app.close)
        self.task = self.app.register_task(ParrotTask())
        self.task.cache = MemoryCache()

    def test_registered_instance_preserves_class(self):
        self.assertIs(self.app.tasks[ParrotTask.name], self.task)
        self.assertTrue(issubclass(ParrotTask, Task))
        self.assertIs(self.task.app, self.app)

    def test_delay_executes_and_persists_eager_result(self):
        result = self.task.delay(result=42)

        self.assertEqual(result.get(), 42)
        self.assertEqual(self.task.AsyncResult(result.id).state, SUCCESS)
        self.assertEqual(self.task.AsyncResult(result.id).result, 42)

    def test_apply_async_accepts_omitted_arguments(self):
        class NoArgumentsTask(ParrotTask):
            name = 'jobtastic.tests.NoArgumentsTask'
            significant_kwargs = []

            def calculate_result(self):
                return 42

        task = self.app.register_task(NoArgumentsTask())
        task.cache = MemoryCache()

        self.assertEqual(task.apply_async().get(), 42)

    def test_apply_async_forwards_options(self):
        self.app.conf.task_always_eager = False
        result = self.app.AsyncResult('forwarded-id')
        with patch.object(Task, 'apply_async', return_value=result) as dispatch:
            self.task.apply_async(kwargs={'result': 42}, queue='reports', countdown=5)

        dispatch.assert_called_once_with((), {'result': 42}, queue='reports', countdown=5)

    def test_cache_key_preserves_class_based_prefix(self):
        self.assertEqual(
            self.task._get_cache_key(result=42),
            ParrotTask._get_cache_key(result=42),
        )
        self.assertTrue(self.task._get_cache_key(result=42).startswith(
            'jobtastic.tests.test_celery54.ParrotTask:',
        ))

    def test_cached_success_reuses_result(self):
        self.task.cache_duration = 60
        first = self.task.delay(result=42)

        with patch.object(self.task, 'calculate_result') as calculate:
            second = self.task.delay(result=42)

        self.assertEqual(second.id, first.id)
        self.assertEqual(second.get(), 42)
        calculate.assert_not_called()

    def test_pending_duplicate_reuses_result(self):
        self.app.conf.task_always_eager = False
        first = self.task.delay(result=42)

        with patch.object(Task, 'apply_async') as dispatch:
            second = self.task.delay(result=42)

        self.assertEqual(second.id, first.id)
        self.assertEqual(second.state, PENDING)
        dispatch.assert_not_called()

    def test_failure_removes_herd_key(self):
        cache_key = self.task._get_cache_key(result=42)
        self.task.cache.set(f'herd:{cache_key}', 'failed-id')
        with patch.object(self.task, 'calculate_result', side_effect=ValueError('bad input')):
            result = self.task.apply(kwargs={'result': 42})

        self.assertEqual(result.state, FAILURE)
        self.assertIsNone(self.task.cache.get(f'herd:{cache_key}'))

    def test_progress_payload_is_preserved(self):
        def calculate(result):
            self.task.update_progress(completed_count=1, total_count=2)
            return result

        with patch.object(self.task, 'calculate_result', side_effect=calculate):
            with patch.object(self.task, 'update_state') as update:
                self.task.delay(result=42)

        progress_calls = [
            call for call in update.call_args_list if call.args[1] == PROGRESS
        ]
        self.assertEqual(progress_calls[0].args[2], {
            'progress_percent': 0,
            'time_remaining': -1,
        })
        self.assertEqual(progress_calls[1].args[2]['progress_percent'], 50)
        self.assertEqual(
            set(progress_calls[1].args[2]),
            {'progress_percent', 'time_remaining'},
        )

    def test_delay_or_run_returns_fallback_pair(self):
        with patch.object(self.task, 'apply_async', side_effect=OperationalError('offline')):
            with self.assertWarns(DeprecationWarning):
                result, fallback = self.task.delay_or_run(result=42)

        self.assertEqual(result, 42)
        self.assertTrue(fallback)

    def test_delay_or_run_returns_async_pair(self):
        with self.assertWarns(DeprecationWarning):
            result, fallback = self.task.delay_or_run(result=42)

        self.assertEqual(result.get(), 42)
        self.assertFalse(fallback)

    def test_eager_fallback_helpers(self):
        for helper in ('async_or_eager', 'delay_or_eager'):
            with self.subTest(helper=helper):
                with patch.object(
                    self.task, 'apply_async', side_effect=OperationalError('offline'),
                ):
                    if helper == 'async_or_eager':
                        result = self.task.async_or_eager(kwargs={'result': 42})
                    else:
                        result = self.task.delay_or_eager(result=42)

                self.assertEqual(result.get(), 42)
                self.assertEqual(self.task.AsyncResult(result.id).state, SUCCESS)

    def test_failure_helpers_persist_failed_result(self):
        for helper in ('async_or_fail', 'delay_or_fail'):
            with self.subTest(helper=helper):
                with patch.object(
                    self.task, 'apply_async', side_effect=OperationalError('offline'),
                ):
                    if helper == 'async_or_fail':
                        result = self.task.async_or_fail(kwargs={'result': 42})
                    else:
                        result = self.task.delay_or_fail(result=42)

                self.assertEqual(result.state, FAILURE)
                self.assertIn('offline', str(result.result))

    def test_unexpected_dispatch_error_propagates(self):
        for helper in ('delay_or_eager', 'delay_or_fail', 'delay_or_run'):
            with self.subTest(helper=helper):
                with patch.object(self.task, 'apply_async', side_effect=ValueError('bad')):
                    with self.assertRaisesRegex(ValueError, 'bad'):
                        getattr(self.task, helper)(result=42)

    def test_cache_is_not_shared_between_instances(self):
        other_app = Celery('other-test', set_as_current=False)
        self.addCleanup(other_app.close)
        other_cache = MemoryCache()
        other_app.conf.jobtastic_cache = other_cache
        other = other_app.register_task(ParrotTask())

        self.assertIs(other.cache, other_cache)
        self.assertIsNot(other.cache, self.task.cache)

    def test_namespaced_cache_configuration(self):
        app = Celery('namespaced-test', set_as_current=False)
        self.addCleanup(app.close)
        app.config_from_object({'CELERY_JOBTASTIC_CACHE': 'shared'}, namespace='CELERY')

        self.assertIs(get_cache(app).cache, caches['shared'])

    def test_legacy_cache_configuration(self):
        self.app.conf['JOBTASTIC_CACHE'] = 'shared'

        self.assertIs(get_cache(self.app).cache, caches['shared'])

    def test_invalid_cache_alias_fails_explicitly(self):
        self.app.conf.jobtastic_cache = 'missing-cache'

        with self.assertRaises(InvalidCacheBackendError):
            get_cache(self.app)
