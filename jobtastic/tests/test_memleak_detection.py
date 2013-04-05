import mock
from unittest2 import TestCase

from testproj.someapp import tasks as mem_tasks


class MemoryGrowthTest(TestCase):
    def setUp(self):
        self.task = mem_tasks.MemLeakyTask()

    def tearDown(self):
        # Reset the variable that leaks memory
        mem_tasks.leaky_global = []

    def test_sanity(self):
        # The task actually runs
        self.assertEqual(self.task.run(bloat_factor=0), 0)

    @mock.patch.object(
        mem_tasks.MemLeakyTask,
        'warn_of_memory_leak',
        autospec=True,
        side_effect=mem_tasks.MemLeakyTask.warn_of_memory_leak,
    )
    def test_below_threshold(self, mock_warn_of_memory_leak):
        # If there's less than the threshold in growth, we don't spit out any
        # warnings
        self.assertEqual(self.task.run(bloat_factor=1), 1)
        # We should have logged no warnings as a result of this
        self.assertEqual(mock_warn_of_memory_leak.call_count, 0)

    @mock.patch.object(
        mem_tasks.MemLeakyTask,
        'warn_of_memory_leak',
        autospec=True,
    )
    def test_above_threshold(self, mock_warn_of_memory_leak):
        self.assertEqual(self.task.run(bloat_factor=5), 5)
        self.assertEqual(mock_warn_of_memory_leak.call_count, 1)

    @mock.patch.object(
        mem_tasks.MemLeakyTask,
        'warn_of_memory_leak',
        autospec=True,
    )
    def test_triggered_repeatedly_on_increase(self, mock_warn_of_memory_leak):
        self.assertEqual(self.task.run(bloat_factor=5), 5)
        self.assertEqual(mock_warn_of_memory_leak.call_count, 1)

        self.assertEqual(self.task.run(bloat_factor=5), 5)
        self.assertEqual(mock_warn_of_memory_leak.call_count, 2)

    @mock.patch.object(
        mem_tasks.MemLeakyTask,
        'warn_of_memory_leak',
        autospec=True,
        side_effect=mem_tasks.MemLeakyTask.warn_of_memory_leak,
    )
    def test_only_triggered_on_change(self, mock_warn_of_memory_leak):
        self.assertEqual(self.task.run(bloat_factor=5), 5)
        self.assertEqual(mock_warn_of_memory_leak.call_count, 1)

        self.assertEqual(self.task.run(bloat_factor=0), 0)
        # There are no extra warnings
        self.assertEqual(mock_warn_of_memory_leak.call_count, 1)

    @mock.patch.object(
        mem_tasks.MemLeakyDefaultedTask,
        'warn_of_memory_leak',
        autospec=True,
        side_effect=mem_tasks.MemLeakyDefaultedTask.warn_of_memory_leak,
    )
    def test_defaults_disabled(self, mock_warn_of_memory_leak):
        self.assertEqual(
            mem_tasks.MemLeakyDefaultedTask().run(bloat_factor=5),
            5,
        )
        self.assertEqual(mock_warn_of_memory_leak.call_count, 0)

    @mock.patch.object(
        mem_tasks.MemLeakyDisabledWarningTask,
        'warn_of_memory_leak',
        autospec=True,
    )
    def test_disabled_with_negative_config(self, mock_warn_of_memory_leak):
        self.assertEqual(
            mem_tasks.MemLeakyDisabledWarningTask().run(bloat_factor=5),
            5,
        )
        self.assertEqual(mock_warn_of_memory_leak.call_count, 0)
