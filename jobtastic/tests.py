import time

from jobtastic.task import JobtasticTask


class TimeoutTestTask(JobtasticTask):
    significant_kwargs = ()
    herd_avoidance_timeout = 10
    task_timeout = 1  # Force the task to timeout after one second.

    def calculate_result(*args, **kwargs):
        # Just sleep
        time.sleep(3)


def test_timeout():
    task = TimeoutTestTask()

    # Call run directly
    start_time = time.time()
    task.run()
    end_time = time.time()

    total_time = end_time - start_time
    assert total_time < 2


def test_timeout_result():
    task = TimeoutTestTask()

    # Call run directly
    result = task.run()

    assert result == {'timed_out': True, 'result': ''}
