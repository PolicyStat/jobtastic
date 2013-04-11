
import mock
from unittest2 import TestCase

from celery import states

from testproj.someapp import tasks


class BrokenBrokerTestCase(TestCase):
    def setUp(self):
        from django.conf import settings
        self.old_setting = settings.CELERY_ALWAYS_EAGER
        self.old_url = settings.BROKER_URL
        # The purpose of the next two lines is to create a situation
        # in which the task fallbacks are run instead
        # In order for this situation to occur, celery cannot be in 'eager'
        # mode, and redis needs to be 'down'.
        settings.CELERY_ALWAYS_EAGER = False
        # Modifying the broken host name simulates the task broker being
        # 'unresponsive'
        settings.BROKER_URL = 'thisbreaksthebroker'

        self.task = tasks.ParrotTask()
        app = self.task._get_app()
        app.conf.CELERY_ALWAYS_EAGER = False

        # TODO: Figure out how to mock `app.producer_or_acquire` so that we can
        # use a broken `publish_task` to trigger errors.
        # https://github.com/celery/celery/blob/master/celery/app/task.py#L478

    def tearDown(self):
        from django.conf import settings
        settings.CELERY_ALWAYS_EAGER = self.old_setting
        settings.BROKER_URL = self.old_url

    @mock.patch.object(
        tasks.ParrotTask,
        'calculate_result',
        autospec=True,
        side_effect=AssertionError("Should have skipped calculate_result"),
    )
    def test_delay_or_fail(self, mock_calculate_result):
        # If there's less than the threshold in growth, we don't spit out any
        # warnings
        async_result = self.task.delay_or_fail(result=1)
        self.assertEqual(async_task.status, states.FAILURE)

    @mock.patch.object(
        tasks.ParrotTask,
        'calculate_result',
        autospec=True,
        return_value=27,
    )
    def test_delay_or_run(self, mock_calculate_result):
        async_result = self.task.delay_or_fail(result=1)
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 27)


class WorkingBrokerTestCase(TestCase):
    def setUp(self):
        self.task = tasks.ParrotTask()

    def test_sanity(self):
        # The task actually runs
        async_task = self.task.delay(result=1)
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 1)

    @mock.patch.object(
        tasks.ParrotTask,
        'calculate_result',
        autospec=True,
        return_value=1,
    )
    def test_delay_or_fail_runs(self, mock_calculate_result):
        async_result = self.task.delay_or_fail(result=1)
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 1)

        self.assertEqual(mock_calculate_result.call_count, 1)

    @mock.patch.object(
        tasks.ParrotTask,
        'calculate_result',
        autospec=True,
        return_value=1,
    )
    def test_delay_or_run_runs(self, mock_calculate_result):
        async_result = self.task.delay_or_fail(result=1)
        self.assertEqual(async_task.status, states.SUCCESS)
        self.assertEqual(async_task.result, 1)

        self.assertEqual(mock_calculate_result.call_count, 1)
