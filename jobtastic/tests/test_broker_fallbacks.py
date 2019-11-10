from __future__ import print_function
import os

import mock


from celery import states
from celery._state import get_current_app
# eager_tasks was removed in celery 3.1
from jobtastic import JobtasticTask
from django.test import TestCase

try:
    from kombu.transport.pyamqp import (
        Channel as AmqpChannel,
    )
except ImportError:
    from kombu.transport.amqplib import (
        Channel as AmqpChannel,
    )
# Kombu>=2.1 doesn't have StdConnectionError or StdChannelError, but the 2.1
# amqp Transport uses an IOError, so we'll just test with that.
try:
    from kombu.exceptions import StdChannelError
except ImportError:
    StdChannelError = IOError
try:
    from kombu.exceptions import StdConnectionError
except ImportError:
    StdConnectionError = IOError


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


error_if_calculate_result_patch = mock.patch.object(
    ParrotTask,
    'calculate_result',
    autospec=True,
    side_effect=AssertionError("Should have skipped calculate_result"),
)
basic_publish_connection_error_patch = mock.patch.object(
    AmqpChannel,
    'basic_publish',
    autospec=True,
    side_effect=StdConnectionError("Should be handled"),
)
basic_publish_channel_error_patch = mock.patch.object(
    AmqpChannel,
    'basic_publish',
    autospec=True,
    side_effect=StdChannelError("Should be handled"),
)


class BrokenBrokerTestCase(TestCase):
    def _set_broker_host(self, new_value):
        os.environ['CELERY_BROKER_URL'] = new_value
        self.app.conf['BROKER_URL'] = new_value
        self.app.conf['BROKER_WRITE_URL'] = new_value
        self.app.conf['BROKER_READ_URL'] = new_value

    def setUp(self):
        self.app = get_current_app()

        self.old_broker_host = self.app.conf.BROKER_HOST or ''

        # Modifying the broken host name simulates the task broker being
        # 'unresponsive'
        # We need to make this modification in 3 places because of version
        # backwards compatibility
        self._set_broker_host('amqp://')
        self.app.conf['CELERY_TASK_PUBLISH_RETRY'] = False

        self.app._pool = None
        # Deleting the cache AMQP class so that it gets recreated with the new
        # BROKER_URL
        del self.app.amqp

        self.task = ParrotTask

    def tearDown(self):
        del self.app.amqp
        self.app._pool = None

        self._set_broker_host(self.old_broker_host)

    def test_sanity(self):
        try:
            result = self.task.delay()
        except IOError:
            pass  # Celery 3
        except KeyError:
            pass  # Celery 2.5
        else:
            print(result)
            raise AssertionError('Exception should have been raised')

    @error_if_calculate_result_patch
    def test_async_or_fail_bad_connection(self, mock_calculate_result):
        # Loop through all of the possible connection errors and ensure they're
        # properly handled
        with basic_publish_connection_error_patch:
            async_task = self.task.async_or_fail(kwargs={"result": 1})
        self.assertEqual(async_task.status, states.FAILURE)

    @error_if_calculate_result_patch
    def test_async_or_fail_bad_channel(self, mock_calculate_result):
        with basic_publish_channel_error_patch:
            async_task = self.task.async_or_fail(kwargs={"result": 1})
        self.assertEqual(async_task.status, states.FAILURE)

    def test_async_or_eager_bad_connection(self):
        with basic_publish_connection_error_patch:
            async_task = self.task.async_or_eager(kwargs={"result": 27})
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 27)

    def test_async_or_eager_bad_channel(self):
        with basic_publish_channel_error_patch:
            async_task = self.task.async_or_eager(kwargs={"result": 27})
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 27)

    @error_if_calculate_result_patch
    def test_delay_or_fail_bad_connection(self, mock_calculate_result):
        # Loop through all of the possible connection errors and ensure they're
        # properly handled
        with basic_publish_connection_error_patch:
            async_task = self.task.delay_or_fail(result=1)
        self.assertEqual(async_task.status, states.FAILURE)

    @error_if_calculate_result_patch
    def test_delay_or_fail_bad_channel(self, mock_calculate_result):
        with basic_publish_channel_error_patch:
            async_task = self.task.delay_or_fail(result=1)
        self.assertEqual(async_task.status, states.FAILURE)

    def test_delay_or_run_bad_connection(self):
        with basic_publish_connection_error_patch:
            async_task, was_fallback = self.task.delay_or_run(result=27)
        self.assertTrue(was_fallback)
        self.assertEqual(async_task, 27)

    def test_delay_or_run_bad_channel(self):
        with basic_publish_channel_error_patch:
            async_task, was_fallback = self.task.delay_or_run(result=27)
        self.assertTrue(was_fallback)
        self.assertEqual(async_task, 27)

    def test_delay_or_eager_bad_connection(self):
        with basic_publish_connection_error_patch:
            async_task = self.task.delay_or_eager(result=27)
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 27)

    def test_delay_or_eager_bad_channel(self):
        with basic_publish_channel_error_patch:
            async_task = self.task.delay_or_eager(result=27)
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 27)


calculate_result_returns_one_patch = mock.patch.object(
    ParrotTask,
    'calculate_result',
    autospec=True,
    return_value=1,
)


class WorkingBrokerTestCase(TestCase):
    def setUp(self):
        self.task = ParrotTask

    def test_sanity(self):
        # The task actually runs
        with self.settings(CELERY_ALWAYS_EAGER=True):
            async_task = self.task.delay(result=1)
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 1)

    @calculate_result_returns_one_patch
    def test_async_or_fail_runs(self, mock_calculate_result):
        with self.settings(CELERY_ALWAYS_EAGER=True):
            async_task = self.task.async_or_fail(kwargs={"result": 1})
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 1)

        self.assertEqual(mock_calculate_result.call_count, 1)

    @calculate_result_returns_one_patch
    def test_async_or_eager_runs(self, mock_calculate_result):
        with self.settings(CELERY_ALWAYS_EAGER=True):
            async_task = self.task.async_or_eager(kwargs={"result": 1})
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 1)

        self.assertEqual(mock_calculate_result.call_count, 1)

    @calculate_result_returns_one_patch
    def test_delay_or_fail_runs(self, mock_calculate_result):
        with self.settings(CELERY_ALWAYS_EAGER=True):
            async_task = self.task.delay_or_fail(result=1)
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 1)

        self.assertEqual(mock_calculate_result.call_count, 1)

    @calculate_result_returns_one_patch
    def test_delay_or_run_runs(self, mock_calculate_result):
        with self.settings(CELERY_ALWAYS_EAGER=True):
            async_task, _ = self.task.delay_or_run(result=1)
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 1)

        self.assertEqual(mock_calculate_result.call_count, 1)

    @calculate_result_returns_one_patch
    def test_delay_or_eager_runs(self, mock_calculate_result):
        with self.settings(CELERY_ALWAYS_EAGER=True):
            async_task = self.task.delay_or_eager(result=1)
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 1)

        self.assertEqual(mock_calculate_result.call_count, 1)
