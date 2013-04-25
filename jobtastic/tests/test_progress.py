
import mock

from celery.result import BaseAsyncResult
from celery.states import SUCCESS
from celery.tests.utils import AppCase, eager_tasks

from jobtastic import JobtasticTask
from jobtastic.states import PROGRESS


class ProgressTask(JobtasticTask):
    """
    Just count up to the given number, with hooks for testing.
    """
    significant_kwargs = [
        ('count_to', str),
    ]
    herd_avoidance_timeout = 0

    def calculate_result(self, count_to, **kwargs):
        update_frequency = 2
        for counter in xrange(count_to):
            self.update_progress(
                counter,
                count_to,
                update_frequency=update_frequency,
            )

        return count_to


def task_status_is_progress(self, **kwargs):
    task_id = self.request.id
    meta = BaseAsyncResult(task_id)

    assert meta.status == PROGRESS


class ProgressTestCase(AppCase):
    def setup(self):
        self.task = ProgressTask

    def test_sanity(self):
        # The task actually runs
        with eager_tasks():
            async_task = self.task.delay(count_to=2)
        self.assertEqual(async_task.status, SUCCESS)
        self.assertEqual(async_task.result, 2)

    def test_starts_with_progress_state(self):
        # The state has already been set to PROGRESS before `calculate_result`
        # starts
        with eager_tasks():
            with mock.patch.object(
                self.task,
                'calculate_result',
                autospec=True,
                side_effect=task_status_is_progress,
            ):
                async_task = self.task.delay(count_to=2)
        # And the state should still be set to SUCCESS in the end
        self.assertEqual(async_task.status, SUCCESS)
