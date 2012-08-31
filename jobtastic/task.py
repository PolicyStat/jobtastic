"""
Celery base task aimed at longish-running jobs that return a result.

``JobtasticTask`` adds thundering herd avoidance, result caching, progress
reporting, error fallback and JSON encoding of results.
"""
from __future__ import division

import logging
import time
from contextlib import contextmanager
from hashlib import md5

from celery import states
from celery.backends import default_backend
from celery.task import Task
from celery.result import BaseAsyncResult
from celery.signals import task_prerun, task_postrun

HAS_DJANGO = False
HAS_WERKZEUG = False
try:
    # For now, let's just say that if Django exists, we should use it.
    # Otherwise, try Flask. This definitely needs an actual configuration
    # variable so folks can make an explicit decision.
    from django.core.cache import cache
    HAS_DJANGO = True
except ImportError:
    pass

if not HAS_DJANGO:
    try:
        # We should really have an explicitly-defined way of doing this, but for
        # now, let's just use werkzeug Memcached if it exists
        from werkzeug.contrib.cache import MemcachedCache

        from celery import conf
        if conf.CELERY_RESULT_BACKEND == 'cache':
            uri_str = conf.CELERY_CACHE_BACKEND.strip('memcached://')
            uris = uri_str.split(';')
            cache = MemcachedCache(uris)
            HAS_WERKZEUG = True
    except ImportError:
        pass

if not HAS_DJANGO and not HAS_WERKZEUG:
    raise Exception(
        "Jobtastic requires either Django or Flask + Memcached result backend")


from jobtastic.states import PROGRESS

@contextmanager
def acquire_lock(lock_name):
    """
    A contextmanager to wait until an exclusive lock is available,
    hold the lock and then release it when the code under context
    is complete.

    TODO: This code doesn't work like it should. It doesn't
    wait indefinitely for the lock and in fact cycles through
    very quickly.
    """
    for _ in range(10):
        try:
            value = cache.incr(lock_name)
        except ValueError:
            cache.set(lock_name, 0)
            value = cache.incr(lock_name)
        if value == 1:
            break
        else:
            cache.decr(lock_name)
    else:
        yield
        cache.set(lock_name, 0)
        return
    yield
    cache.decr(lock_name)



class JobtasticTask(Task):
    """
    A base ``Celery.Task`` class that provides some common niceties for running
    tasks that return some kind of result for which you need to wait.

    To create a task that uses these helpers, use ``JobtasticTask`` as a
    subclass and define a ``calculate_result`` method which returns a
    dictionary to be turned in to JSON. You will also need to define the
    following class variables:

    * ``significant_kwargs`` The kwarg values that will be converted to strings
      and hashed to determine if two versions of the same task are equivalent.
      This is a list of 2-tuples with the first item being the kwarg string and
      the second being a callable that converts the value to a hashable string.
      If no second item is given, it's assumed that calling ``str()`` on the
      value works just fine.
    * ``herd_avoidance_timeout`` Number of seconds to hold a lock on this task
      for other equivalent runs. Generally, this should be set to the longest
      estimated amount of time the task could consume.

    The following class members are optional:
    * ``cache_prefix`` A unique string representing this task. Eg.
      ``foo.bar.tasks.BazzTask``
    * ``cache_duration`` The number of seconds for which the result of this
      task should be cached, meaning subsequent equivalent runs will skip
      computation. The default is to do no result caching.

    Provided are helpers for:

    1. Handling failures to connect the task broker by either directly
      running the task (`delay_or_run`) or by returning a task that
      contains the connection error (`delay_or_fail`). This minimizes
      the user-facing impact of a dead task broker.
    2. Defeating any thundering herd issues by ensuring only one of a task with
      specific arguments can be running at a time by directing subsequent calls
      to latch on to the appropriate result.
    3. Caching the final result for a designated time period so that subsequent
      equivalent calls return quickly.
    4. Returning the results as JSON, so that they can be processed easily by
      client-side javascript.
    5. Returning time-based, continually updating progress estimates to
      front-end code so that users know what to expect.
    """
    abstract = True

    def delay_or_run(self, *args, **kwargs):
        """
        Attempt to call self.delay, or if that fails, call self.run.

        Returns a tuple, (result, fallback). ``result`` is the result of
        calling delay or run. ``fallback`` is a boolean that is True when
        self.run was called instead of self.delay.
        """
        try:
            result = self.delay(*args, **kwargs)
            fallback = False
        except IOError:
            result = self.run(*args, **kwargs)
            fallback = True
        return result, fallback

    def delay_or_fail(self, *args, **kwargs):
        """
        Attempt to call self.delay, but if that fails with an exception, we
        fake the task completion using the exception as the result. This allows
        us to seamlessly handle errors on task creation the same way we handle
        errors when a task runs, simplifying the user interface.
        """
        try:
            return self.delay(*args, **kwargs)
        except IOError as e:
            # Take this exception and store it as an async result. This means that
            # errors connecting the broker can be handled with the same client-side code
            # that handles error that occur on workers.
            self.backend.store_result(
                self.task_id, exception, status=states.FAILURE)

            return BaseAsyncResult(self.task_id, self.backend)

    def delay(self, *args, **kwargs):
        """
        Put this task on the Celery queue as a singleton. Only one of this type
        of task with its distinguishing args/kwargs will be allowed on the
        queue at a time. Subsequent duplicate tasks called while this task is
        still running will just latch on to the results of the running task by
        synchronizing the task uuid. Additionally, identical task calls will
        return those results for the next ``cache_duration`` seconds.

        Passing a ``cache_duration`` keyword argument controls how long
        identical task calls will latch on to previously cached results.
        """
        self._validate_required_class_vars()

        cache_key = self._get_cache_key(**kwargs)

        # Check for an already-computed and cached result
        task_id = cache.get(cache_key)  # Check for the cached result
        if task_id:
            # We've already built this result, just latch on to the task that
            # did the work
            logging.info(
                'Found existing cached and completed task: %s', task_id)
            return BaseAsyncResult(task_id, self.backend)

        # Check for an in-progress equivalent task to avoid duplicating work
        task_id = cache.get('herd:%s' % cache_key)
        if task_id:
            logging.info('Found existing in-progress task: %s', task_id)
            return BaseAsyncResult(task_id, self.backend)

        # It's not cached and it's not already running. Use an atomic lock to
        # start the task, ensuring there isn't a race condition that could
        # result in multiple identical tasks being fired at once.
        with acquire_lock('lock:%s' % cache_key):
            task_meta = super(JobtasticTask, self).delay(
                *args, **kwargs)
            logging.info('Current status: %s', task_meta.status)
            if task_meta.status in [PROGRESS, states.PENDING]:
                cache.set(
                    'herd:%s' % cache_key,
                    task_meta.task_id,
                    timeout=self.herd_avoidance_timeout)
                logging.info(
                    'Setting herd-avoidance cache for task: %s', cache_key)
        return task_meta

    def calc_progress(self, completed_count, total_count):
        """
        Calculate the percentage progress and estimated remaining time based on
        the current number of items completed of the total.

        Returns a tuple of ``(percentage_complete, seconds_remaining)``.
        """
        self.logger.debug(
            "calc_progress(%s, %s)",
            completed_count,
            total_count,
        )
        current_time = time.time()

        time_spent = current_time - self.start_time
        self.logger.debug("Progress time spent: %s", time_spent)

        if total_count == 0:
            return 100, 1

        completion_fraction = completed_count / total_count
        if completion_fraction == 0:
            completion_fraction = 1

        total_time = 0
        total_time = time_spent / completion_fraction
        time_remaining = total_time - time_spent

        completion_display = completion_fraction * 100
        if completion_display == 100:
            return 100, 1  # 1 second to finish up

        return completion_display, time_remaining

    def update_progress(self, completed_count, total_count, update_frequency=1):
        """
        Update the task backend with both an estimated percentage complete and
        number of seconds remaining until completion.

        ``completed_count`` Number of task "units" that have been completed out
        of ``total_count`` total "units."
        ``update_frequency`` Only actually store the updated progress in the
        background at most every ``N`` ``completed_count``.
        """
        if completed_count - self._last_update_count < update_frequency:
            # We've updated the progress too recently. Don't stress out the
            # result backend
            return
        # Store progress for display
        progress_percent, time_remaining = self.calc_progress(
            completed_count, total_count)
        self.logger.info(
            "Updating progress: %s percent, %s remaining",
            progress_percent,
            time_remaining)
        self.backend.store_result(
            self.task_id,
            result={
                "progress_percent": progress_percent,
                "time_remaining": time_remaining,
            },
            status=PROGRESS)

    def run(self, *args, **kwargs):
        self.logger = self.get_logger(**kwargs)
        self.logger.info("Starting %s", self.__class__.__name__)

        self.cache_key = self._get_cache_key(**kwargs)

        # Record start time to give estimated time remaining estimates
        self.start_time = time.time()

        # Keep track of progress updates for update_frequency tracking
        self._last_update_count = 0

        # Report to the backend that work has been started.
        self.task_id = kwargs.get('task_id', None)
        if self.task_id is not None:
            self.backend.store_result(
                self.task_id,
                result={
                    "progress_percent": 0,
                    "time_remaining": -1,
                },
                status=PROGRESS,
            )

        self.logger.info("Calculating result")
        try:
            task_result = self.calculate_result(*args, **kwargs)
        except Exception:
            # Don't want other tasks waiting for this task to finish, since it
            # won't
            self._break_thundering_herd_cache()
            raise  # We can use normal celery exception handling for this

        if hasattr(self, 'cache_duration'):
            cache_duration = self.cache_duration
        else:
            cache_duration = -1  # By default, don't cache
        if cache_duration >= 0 and self.task_id is not None:
            # If we're configured to cache this result, do so.
            cache.set(self.cache_key, self.task_id, cache_duration)

        # Now that the task is finished, we can stop all of the thundering herd
        # avoidance
        self._break_thundering_herd_cache()

        return task_result

    def calculate_result(self, *args, **kwargs):
        raise NotImplementedError(
            "Tasks using JobtasticTask must implement their own calculate_result")

    def _validate_required_class_vars(self):
        """
        Ensure that this subclass has defined all of the required class
        variables.
        """
        required_members = [
            'significant_kwargs',
            'herd_avoidance_timeout',
        ]
        for required_member in required_members:
            if not hasattr(self, required_member):
                raise Exception(
                    "JobtasticTask's must define a %s" % required_member)

    def on_success(self, retval, task_id, args, kwargs):
        """
        Store results in the backend even if we're always eager. This ensures
        the `delay_or_run` calls always at least have results.
        """
        if self.request.is_eager:
            # Store the result because celery wouldn't otherwise
            self.backend.store_result(task_id, retval, status=states.SUCCESS)

    def _break_thundering_herd_cache(self):
        cache.delete('herd:%s' % self.cache_key)

    def _get_cache_key(self, **kwargs):
        """
        Take this task's configured ``significant_kwargs`` and build a hash
        that all equivalent task calls will match.

        Takes in kwargs and returns a string.

        To change the way the cache key is generated or do more in-depth
        processing, override this method.
        """
        m = md5()
        for significant_kwarg in self.significant_kwargs:
            key, to_str = significant_kwarg
            m.update(to_str(kwargs[key]))

        if hasattr(self, 'cache_prefix'):
            cache_prefix = self.cache_prefix
        else:
            cache_prefix = '%s.%s' % (self.__module__, self.__name__)
        return '%s:%s' % (cache_prefix, m.hexdigest())
