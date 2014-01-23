from __future__ import with_statement

from contextlib import contextmanager
from functools import wraps

from celery.app import app_or_default


# Ported from Celery 3.0, because this was removed in Celery 3.1
@contextmanager
def eager_tasks():
    app = app_or_default()

    prev = app.conf.CELERY_ALWAYS_EAGER
    app.conf.CELERY_ALWAYS_EAGER = True
    try:
        yield True
    finally:
        app.conf.CELERY_ALWAYS_EAGER = prev


def with_eager_tasks(fun):

    @wraps(fun)
    def _inner(*args, **kwargs):
        app = app_or_default()
        prev = app.conf.CELERY_ALWAYS_EAGER
        app.conf.CELERY_ALWAYS_EAGER = True
        try:
            return fun(*args, **kwargs)
        finally:
            app.conf.CELERY_ALWAYS_EAGER = prev
