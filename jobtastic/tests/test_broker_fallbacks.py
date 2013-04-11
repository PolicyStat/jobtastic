
import mock
from unittest2 import TestCase

from celery import states
from celery.tests.utils import AppCase, with_eager_tasks

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


class BrokenBrokerTestCase(AppCase):
    def setup(self):
        # lowercase on purpose. AppCase calls `self.setup`
        from nose.tools import set_trace; set_trace()
        self.app._pool = None
        # Deleting the cache AMQP class so that it gets recreated with the new
        # BROKER_URL
        del self.app.amqp

        self.old_broker_url = self.app.conf.BROKER_URL

        # Modifying the broken host name simulates the task broker being
        # 'unresponsive'
        self.app.conf.BROKER_URL = 'thisbreaksthebroker'

        self.task = ParrotTask()

        # TODO: Figure out how to mock `app.producer_or_acquire` so that we can
        # use a broken `publish_task` to trigger errors.
        # https://github.com/celery/celery/blob/master/celery/app/task.py#L478

    def teardown(self):
        del self.app.amqp
        self.app._pool = None
        self.app.conf.BROKER_URL = self.old_broker_url

    @mock.patch.object(
        ParrotTask,
        'calculate_result',
        autospec=True,
        side_effect=AssertionError("Should have skipped calculate_result"),
    )
    def test_delay_or_fail(self, mock_calculate_result):
        # If there's less than the threshold in growth, we don't spit out any
        # warnings
        async_task = self.task.delay_or_fail(result=1)
        self.assertEqual(async_task.status, states.FAILURE)

    @mock.patch.object(
        ParrotTask,
        'calculate_result',
        autospec=True,
        return_value=27,
    )
    def test_delay_or_run(self, mock_calculate_result):
        async_task = self.task.delay_or_fail(result=1)
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 27)


class WorkingBrokerTestCase(AppCase):
    def setup(self):
        self.task = ParrotTask()

    @with_eager_tasks
    def test_sanity(self):
        # The task actually runs
        async_task = self.task.delay(result=1)
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 1)

    @with_eager_tasks
    @mock.patch.object(
        ParrotTask,
        'calculate_result',
        autospec=True,
        return_value=1,
    )
    def test_delay_or_fail_runs(self, mock_calculate_result):
        async_task = self.task.delay_or_fail(result=1)
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 1)

        self.assertEqual(mock_calculate_result.call_count, 1)

    @with_eager_tasks
    @mock.patch.object(
        ParrotTask,
        'calculate_result',
        autospec=True,
        return_value=1,
    )
    def test_delay_or_run_runs(self, mock_calculate_result):
        async_task = self.task.delay_or_fail(result=1)
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 1)

        self.assertEqual(mock_calculate_result.call_count, 1)
