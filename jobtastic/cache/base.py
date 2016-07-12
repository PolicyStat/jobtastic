from contextlib import contextmanager


class BaseCache(object):
    """
    A base class that defines the interface required for a JobTastic cache.

    The cache for a JobTastic Task must be shared across all Celery Workers
    running the Task and application servers submitting the Task.

    It is used for scheduling, thundering herd protection and exclusive locks.
    """

    def get(self, key):
        raise NotImplementedError('Must implement the get method.')

    def set(self, key, value, timeout):
        raise NotImplementedError('Must implement the set method.')

    def delete(self, key):
        raise NotImplementedError('Must implement the delete method')

    def lock(self, lock_name, timeout=900):
        raise NotImplementedError('Must implement a lock context manager')


class WrappedCache(BaseCache):
    """
    A thin wrapper around an existing cache object that supports get/set/delete
    and either atomic add or lock
    """

    cache = None

    def __init__(self, cache):
        self.cache = cache

    def get(self, key):
        return self.cache.get(key)

    def set(self, key, value, timeout=None):
        if timeout:
            return self.cache.set(key, value, timeout)
        else:
            return self.cache.set(key, value)

    def delete(self, key):
        return self.cache.delete(key)

    @contextmanager
    def lock(self, lock_name, timeout=900):
        """
        Attempt to use lock and unlock, which will work if the Cache is Redis,
        but fall back to a memcached-compliant add/delete approach.

        If the Jobtastic Cache isn't Redis or Memcache, or another product
        with a compatible lock or add/delete API, then a custom locking function
        will be required. However, Redis and Memcache are expected to account for
        the vast majority of installations.

        See:
        - http://loose-bits.com/2010/10/distributed-task-locking-in-celery.html
        - http://celery.readthedocs.org/en/latest/tutorials/task-cookbook.html#ensuring-a-task-is-only-executed-one-at-a-time  # NOQA

        """
        # Try Redis first
        try:
            try:
                lock = self.cache.lock
            except AttributeError:
                try:
                    # Possibly using old Django-Redis
                    lock = self.cache.client.lock
                except AttributeError:
                    # Possibly using Werkzeug + Redis
                    lock = self.cache._client.lock
            have_lock = False
            lock = lock(lock_name, timeout=timeout)
            try:
                have_lock = lock.acquire(blocking=True)
                if have_lock:
                    yield
            finally:
                if have_lock:
                    lock.release()
        except AttributeError:
            # No lock method on the cache, so fall back to add
            have_lock = False
            try:
                while not have_lock:
                    have_lock = self.cache.add(lock_name, 'locked', timeout)
                if have_lock:
                    yield
            finally:
                if have_lock:
                    self.cache.delete(lock_name)
