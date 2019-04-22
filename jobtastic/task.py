"""
Celery base task aimed at longish-running jobs that return a result.

``JobtasticTask`` adds thundering herd avoidance, result caching, progress
reporting, error fallback and JSON encoding of results.
"""
from __future__ import division

import logging
import time
import os
import sys
import warnings
from hashlib import md5

import psutil

from billiard.einfo import ExceptionInfo
try:  # Celery 4
    from celery.local import class_property
except ImportError:  # Celery 3
    from celery.five import class_property
from celery.states import PENDING, SUCCESS
from celery.task import Task
from celery.utils import gen_unique_id
from jobtastic.cache import get_cache
from jobtastic.states import PROGRESS  # NOQA

get_task_logger = None
try:
    from celery.utils.log import get_task_logger
except ImportError:
    pass  # get_task_logger is new in Celery 3.X


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
    * ``memleak_threshold`` When a single run of a Task increase the resident
      process memory usage by more than this number of MegaBytes, a warning is
      logged to the logger. This is useful for finding tasks that are behaving
      badly under certain conditions. By default, no logging is performed.
      Set this value to 0 to log all RAM changes and -1 to disable logging.

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

    #: The shared cache used for locking and thundering herd protection
    _cache = None

    @classmethod
    def async_or_eager(self, **options):
        """
        Attempt to call self.apply_async, or if that fails because of a problem
        with the broker, run the task eagerly and return an EagerResult.
        """
        args = options.pop("args", None)
        kwargs = options.pop("kwargs", None)
        possible_broker_errors = self._get_possible_broker_errors_tuple()
        try:
            return self.apply_async(args, kwargs, **options)
        except possible_broker_errors:
            return self.apply(args, kwargs, **options)

    @classmethod
    def async_or_fail(self, **options):
        """
        Attempt to call self.apply_async, but if that fails with an exception,
        we fake the task completion using the exception as the result. This
        allows us to seamlessly handle errors on task creation the same way we
        handle errors when a task runs, simplifying the user interface.
        """
        args = options.pop("args", None)
        kwargs = options.pop("kwargs", None)
        possible_broker_errors = self._get_possible_broker_errors_tuple()
        try:
            return self.apply_async(args, kwargs, **options)
        except possible_broker_errors as e:
            return self.simulate_async_error(e)

    @classmethod
    def delay_or_eager(self, *args, **kwargs):
        """
        Wrap async_or_eager with a convenience signiture like delay
        """
        return self.async_or_eager(args=args, kwargs=kwargs)

    @classmethod
    def delay_or_run(self, *args, **kwargs):
        """
        Attempt to call self.delay, or if that fails, call self.run.

        Returns a tuple, (result, required_fallback). ``result`` is the result
        of calling delay or run. ``required_fallback`` is True if the broker
        failed we had to resort to `self.run`.
        """
        warnings.warn(
            "delay_or_run is deprecated. Please use delay_or_eager",
            DeprecationWarning,
        )
        possible_broker_errors = self._get_possible_broker_errors_tuple()
        try:
            result = self.apply_async(args=args, kwargs=kwargs)
            required_fallback = False
        except possible_broker_errors:
            result = self().run(*args, **kwargs)
            required_fallback = True
        return result, required_fallback

    @classmethod
    def delay_or_fail(self, *args, **kwargs):
        """
        Wrap async_or_fail with a convenience signiture like delay
        """
        return self.async_or_fail(args=args, kwargs=kwargs)

    @classmethod
    def _get_possible_broker_errors_tuple(self):
        if hasattr(self.app, 'connection'):
            dummy_conn = self.app.connection()
        else:
            # Celery 2.5 uses `broker_connection` instead
            dummy_conn = self.app.broker_connection()

        possible_broker_errors = (
            dummy_conn.connection_errors + dummy_conn.channel_errors
        )
        try:
            from kombu.exceptions import OperationalError
            # In celery 4.x when a broker is not connected it throws an
            # OperationalError from kombu. It should also be noted that the
            # newest version of kombu (4.1.0) actually hangs forever. So we
            # need to peg versions of kombu until that gets fixed.
            possible_broker_errors += (OperationalError,)
        except ImportError:
            pass
        return possible_broker_errors

    @classmethod
    def simulate_async_error(self, exception):
        """
        Take this exception and store it as an error in the result backend.
        This unifies the handling of broker-connection errors with any other
        type of error that might occur when running the task. So the same
        error-handling that might retry a task or display a useful message to
        the user can also handle this error.
        """
        task_id = gen_unique_id()
        async_result = self.AsyncResult(task_id)
        einfo = ExceptionInfo(sys.exc_info())

        async_result.backend.mark_as_failure(
            task_id,
            exception,
            traceback=einfo.traceback,
        )

        return async_result

    @classmethod
    def apply_async(self, args, kwargs, **options):
        """
        Put this task on the Celery queue as a singleton. Only one of this type
        of task with its distinguishing args/kwargs will be allowed on the
        queue at a time. Subsequent duplicate tasks called while this task is
        still running will just latch on to the results of the running task by
        synchronizing the task uuid. Additionally, identical task calls will
        return those results for the next ``cache_duration`` seconds.
        """
        self._validate_required_class_vars()

        cache_key = self._get_cache_key(**kwargs)

        # Check for an already-computed and cached result
        task_id = self.cache.get(cache_key)  # Check for the cached result
        if task_id:
            # We've already built this result, just latch on to the task that
            # did the work
            logging.info(
                'Found existing cached and completed task: %s', task_id)
            return self.AsyncResult(task_id)

        # Check for an in-progress equivalent task to avoid duplicating work
        task_id = self.cache.get('herd:%s' % cache_key)
        if task_id:
            logging.info('Found existing in-progress task: %s', task_id)
            return self.AsyncResult(task_id)

        # It's not cached and it's not already running. Use an atomic lock to
        # start the task, ensuring there isn't a race condition that could
        # result in multiple identical tasks being fired at once.
        with self.cache.lock('lock:%s' % cache_key):
            task_meta = super(JobtasticTask, self).apply_async(
                args,
                kwargs,
                **options
            )
            logging.info('Current status: %s', task_meta.status)
            if task_meta.status in (PROGRESS, PENDING):
                self.cache.set(
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

    def update_progress(
        self,
        completed_count,
        total_count,
        update_frequency=1,
    ):
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
        self.logger.debug(
            "Updating progress: %s percent, %s remaining",
            progress_percent,
            time_remaining)
        if self.request.id:
            self._last_update_count = completed_count
            self.update_state(None, PROGRESS, {
                "progress_percent": progress_percent,
                "time_remaining": time_remaining,
            })

    def run(self, *args, **kwargs):
        if get_task_logger:
            self.logger = get_task_logger(self.__class__.__name__)
        else:
            # Celery 2.X fallback
            self.logger = self.get_logger(**kwargs)
        self.logger.info("Starting %s", self.__class__.__name__)

        self.cache_key = self._get_cache_key(**kwargs)

        # Record start time to give estimated time remaining estimates
        self.start_time = time.time()

        # Keep track of progress updates for update_frequency tracking
        self._last_update_count = 0

        # Report to the backend that work has been started.
        if self.request.id:
            self.update_state(None, PROGRESS, {
                "progress_percent": 0,
                "time_remaining": -1,
            })

        memleak_threshold = int(getattr(self, 'memleak_threshold', -1))
        if memleak_threshold >= 0:
            begining_memory_usage = self._get_memory_usage()

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
        if cache_duration >= 0:
            # If we're configured to cache this result, do so.
            self.cache.set(self.cache_key, self.request.id, cache_duration)

        # Now that the task is finished, we can stop all of the thundering herd
        # avoidance
        self._break_thundering_herd_cache()

        if memleak_threshold >= 0:
            self._warn_if_leaking_memory(
                begining_memory_usage,
                self._get_memory_usage(),
                memleak_threshold,
                task_kwargs=kwargs,
            )

        return task_result

    def calculate_result(self, *args, **kwargs):
        raise NotImplementedError((
            "Tasks using JobtasticTask must implement "
            "their own calculate_result"
        ))

    @classmethod
    def _validate_required_class_vars(self):
        """
        Ensure that this subclass has defined all of the required class
        variables.
        """
        required_members = (
            'significant_kwargs',
            'herd_avoidance_timeout',
        )
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
            self.update_state(task_id, SUCCESS, retval)

    def _break_thundering_herd_cache(self):
        self.cache.delete('herd:%s' % self.cache_key)

    @classmethod
    def _get_cache(self):
        """
        Return the cache to use for thundering herd protection, etc.
        """
        if not self._cache:
            self._cache = get_cache(self.app)
        return self._cache

    @classmethod
    def _set_cache(self, cache):
        """
        Set the Jobtastic Cache for the Task

        The cache must support get/set (with timeout)/delete/lock (as a context
        manager).
        """
        self._cache = cache

    cache = class_property(_get_cache, _set_cache)

    @classmethod
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
            try:
                m.update(to_str(kwargs[key]))
            except (TypeError, UnicodeEncodeError):
                # Python 3.x strings aren't accepted by hash.update().
                # String should be byte-encoded first.
                m.update(to_str(kwargs[key]).encode('utf-8'))

        if hasattr(self, 'cache_prefix'):
            cache_prefix = self.cache_prefix
        else:
            cache_prefix = '%s.%s' % (self.__module__, self.__name__)
        return '%s:%s' % (cache_prefix, m.hexdigest())

    def _get_memory_usage(self):
        current_process = psutil.Process(os.getpid())
        usage = current_process.memory_info()

        return usage.rss

    def _warn_if_leaking_memory(
        self, begining_usage, ending_usage, threshold, task_kwargs,
    ):
        growth = ending_usage - begining_usage

        threshold_in_bytes = threshold * 1000000

        if growth > threshold_in_bytes:
            self.warn_of_memory_leak(
                growth,
                begining_usage,
                ending_usage,
                task_kwargs,
            )

    def warn_of_memory_leak(
        self, growth, begining_usage, ending_usage, task_kwargs,
    ):
        self.logger.warning(
            "Jobtastic:memleak memleak_detected. memory_increase=%05d unit=MB",
            growth / 1000000,
        )
        self.logger.info(
            "Jobtastic:memleak memory_usage_start=%05d unit=MB",
            begining_usage / 1000000,
        )
        self.logger.info(
            "Jobtastic:memleak memory_usage_end=%05d unit=MB",
            ending_usage / 1000000,
        )
        self.logger.info(
            "Jobtastic:memleak task_kwargs=%s",
            repr(task_kwargs),
        )
