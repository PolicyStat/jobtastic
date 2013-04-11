Changelog
=========

0.2.0
-----

* `delay_or_eager` is here to replace `delay_or_run`! This applies your tasks
  the same way that Celery does when `CELERY_ALWAYS_EAGER` is configured,
  giving you more consistency. The biggest benefit, though, is that you always
  get a result that behaves like an `AsyncResult` object, meaning you don't
  have to fuss with the `was_fallback` variable. `delay_or_run` is still
  around, but it's deprecated. It will go away with the `0.3.0` release.
* Bug fix: `delay_or_fail` actually works during the failure case, now.
  And we have tests on it so that it will keep working.

0.1.1
-----

* Memory leak detection via ``memleak_threshold``
* Tox and Travis-CI tests!

0.1.0
-----

* A super sweet name. Much better than AwesomeResultTask.
* This changelog
* Hope?
