import os

import mock


from celery import states
from celery.tests.utils import AppCase, eager_tasks

USING_CELERY_2_X = False
try:
    from kombu.transport.pyamqp import (
        Channel as AmqpChannel,
    )
    from kombu.exceptions import StdChannelError, StdConnectionError
except ImportError:
    USING_CELERY_2_X = True
    from kombu.transport.amqplib import (
        Channel as AmqpChannel,
    )
    from kombu.exceptions import StdChannelError
    # Kombu 2.1 doesn' thave a StdConnectionError, but the 2.1 amqp Transport
    # uses an IOError, so we'll just test with that
    StdConnectionError = IOError

from jobtastic import JobtasticTask


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


class BrokenBrokerTestCase(AppCase):
    def _set_broker_host(self, new_value):
        os.environ['CELERY_BROKER_URL'] = new_value
        self.app.conf.BROKER_URL = new_value
        self.app.conf.BROKER_HOST = new_value

    def setup(self):
        # lowercase on purpose. AppCase calls `self.setup`
        self.app._pool = None
        # Deleting the cache AMQP class so that it gets recreated with the new
        # BROKER_URL
        del self.app.amqp

        self.old_broker_host = self.app.conf.BROKER_HOST

        # Modifying the broken host name simulates the task broker being
        # 'unresponsive'
        # We need to make this modification in 3 places because of version
        # backwards compatibility
        self._set_broker_host('amqp://')
        self.app.conf['BROKER_CONNECTION_RETRY'] = False
        self.app.conf['BROKER_POOL_LIMIT'] = 1
        self.app.conf['CELERY_TASK_PUBLISH_RETRY'] = False

        self.task = ParrotTask

    def teardown(self):
        del self.app.amqp
        self.app._pool = None

        self._set_broker_host(self.old_broker_host)

    def test_sanity(self):
        self.assertRaises(IOError, self.task.delay, result=1)

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


class WorkingBrokerTestCase(AppCase):
    def setup(self):
        self.task = ParrotTask

    def test_sanity(self):
        # The task actually runs
        with eager_tasks():
            async_task = self.task.delay(result=1)
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 1)

    @calculate_result_returns_one_patch
    def test_delay_or_fail_runs(self, mock_calculate_result):
        with eager_tasks():
            async_task = self.task.delay_or_fail(result=1)
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 1)

        self.assertEqual(mock_calculate_result.call_count, 1)

    @calculate_result_returns_one_patch
    def test_delay_or_run_runs(self, mock_calculate_result):
        with eager_tasks():
            async_task, _ = self.task.delay_or_run(result=1)
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 1)

        self.assertEqual(mock_calculate_result.call_count, 1)

    @calculate_result_returns_one_patch
    def test_delay_or_eager_runs(self, mock_calculate_result):
        with eager_tasks():
            async_task = self.task.delay_or_eager(result=1)
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 1)

        self.assertEqual(mock_calculate_result.call_count, 1)
