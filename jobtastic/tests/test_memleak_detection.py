import logging

from unittest2 import TestCase

from testproj.someapp import tasks as mem_tasks


class MockLoggingHandler(logging.Handler):
    """
    Mock logging handler to check for expected logs.

    Found at:
    http://stackoverflow.com/q/899067/386925
    """

    def __init__(self, *args, **kwargs):
        self.reset()
        logging.Handler.__init__(self, *args, **kwargs)

    def emit(self, record):
        self.messages[record.levelname.lower()].append(record.getMessage())

    def reset(self):
        self.messages = {
            'debug': [],
            'info': [],
            'warning': [],
            'error': [],
            'critical': [],
        }


class MemoryGrowthTest(TestCase):
    def _get_logger(self):
        return logging.getLogger('celery.task')

    def _get_mem_warning_count(self):
        return len(self.log_handler.messages['warning'])

    def _get_task(self):
        return mem_tasks.MemLeakyTask()

    def setUp(self):
        self.logger = self._get_logger()

        # Add a handler so we can see what messages are added/removed
        self.log_handler = MockLoggingHandler()
        self.logger.addHandler(self.log_handler)

    def tearDown(self):
        self.logger.removeHandler(self.log_handler)

        # Reset the variable that leaks memory
        mem_tasks.leaky_global = {}

    def test_sanity(self):
        # The task actually runs
        task = mem_tasks.MemLeakyTask()
        self.assertEqual(task.run(bloat_factor=0), 0)

    def test_below_threshold(self):
        # If there's less than the threshold in growth, we don't spit out any
        # warnings
        self.assertEqual(mem_tasks.MemLeakyTask().run(bloat_factor=1), 1)
        # We should have logged no warnings as a result of this
        self.assertEqual(self._get_mem_warning_count(), 0)

    def test_above_threshold(self):
        self.assertEqual(mem_tasks.MemLeakyTask().run(bloat_factor=5), 5)
        self.assertEqual(self._get_mem_warning_count(), 1)

    def test_only_triggered_on_change(self):
        self.assertEqual(mem_tasks.MemLeakyTask().run(bloat_factor=5), 5)
        self.assertEqual(self._get_mem_warning_count(), 1)

        self.assertEqual(mem_tasks.MemLeakyTask().run(bloat_factor=0), 0)
        # There are no extra warnings
        self.assertEqual(self._get_mem_warning_count(), 1)
