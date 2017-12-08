from contextlib import contextmanager
import celery
import mock


@contextmanager
def allow_checking_status_for_eager(*args, **kwargs):
    if not celery.VERSION[0] == 4:
        yield
    else:
        # In celery 4.x you cannot retrieve the status of a task if it's eager.
        # This gets around that.
        with mock.patch(
            'celery.backends.base.Backend._ensure_not_eager',
            autospec=True,
        ):
            yield
