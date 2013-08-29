Changelog
=========

0.2.2
-----

* The `update_frequency` argument to `update_progress()` wasn't properly
  delaying updates to the back end after the first increment. This resulted
  in many more progress updates to your backend, which means you should
  see performance gains with this release if you took advantage of that option.
  Thanks to Ilya Baryshev for the fix.
* Logging calls related to `update_progress()` are now at the `DEBUG` level
  instead of `LOG`. Hopefully your logs are much more readable, as a result.
  Thanks to Kyle Gibson for convincing me that things used for debugging
  should probably be at the debug level.

0.2.1
-----

* Progress tracking now works properly in Celery 3.X. Progress tracking
  previously worked in 2.5, but because we relied on behavior that changed in
  3.X to retrieve the task_id for recording the progress, it failed there.
  We've not only fixed that problem (with a test), but also moved to using the
  cleaner `self.update_state` call instead of a `self.backend.store_result`
  call. Thanks to George Marshall for help on the fix.

0.2.0
-----

* We're now overriding the base `Task.async_result` call, instead of the
  `Task.delay` call. This means that if you need to customize some of the
  options only available via `async_result`, you don't lose any of the
  Jobtastic functionality.
* `delay_or_fail` should now consistently detect all types of broker failures,
  regardless of your broker choice.
* `delay_or_eager` is here to replace `delay_or_run`! This applies your tasks
  the same way that Celery does when `CELERY_ALWAYS_EAGER` is configured,
  giving you more consistency. The biggest benefit, though, is that you always
  get a result that behaves like an `AsyncResult` object, meaning you don't
  have to fuss with the `was_fallback` variable. `delay_or_run` is still
  around, but it's deprecated. It will go away with the `0.3.0` release.
* Bug fix: `delay_or_fail` actually works during the failure case, now.
  And we have tests on it so that it will keep working.
* `delay_or_fail` now properly sets the traceback for inspection via
  `get_traceback`.

Backwards Incompatible Changes
++++++++++++++++++++++++++++++

The ``delay_or_FOO`` methods are now proper class methods. Previously, they
were special snowflakes and different from normal Celery tasks, which was bad.
Basically, if you used to have::

    MyTask().delay_or_fail()

now you'll have::

    MyTask.delay_or_fail()

0.1.1
-----

* Memory leak detection via ``memleak_threshold``
* Tox and Travis-CI tests!

0.1.0
-----

* A super sweet name. Much better than AwesomeResultTask.
* This changelog
* Hope?
