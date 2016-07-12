from celery.backends import get_backend_by_url
from celery.backends.cache import CacheBackend
from celery.backends.redis import RedisBackend
from .base import BaseCache, WrappedCache


def get_cache(app):
    """
    Attempt to find a valid cache from the Celery configuration

    If the setting is a valid cache, just use it.
    Otherwise, if Django is installed, then:
        If the setting is a valid Django cache entry, then use that.
        If the setting is empty use the default cache
    Otherwise, if Werkzeug is installed, then:
        If the setting is a valid Celery Memcache or Redis Backend, then use
            that.
        If the setting is empty and the default Celery Result Backend is
            Memcache or Redis, then use that
    Otherwise fail
    """
    jobtastic_cache_setting = app.conf.get('JOBTASTIC_CACHE')
    if isinstance(jobtastic_cache_setting, BaseCache):
        return jobtastic_cache_setting

    # Try Django
    try:
        from django.core.cache import caches, InvalidCacheBackendError
        if jobtastic_cache_setting:
            try:
                return WrappedCache(caches[jobtastic_cache_setting])
            except InvalidCacheBackendError:
                pass
        else:
            return WrappedCache(caches['default'])
    except ImportError:
        pass

    # Try Werkzeug
    try:
        from werkzeug.contrib.cache import MemcachedCache, RedisCache
        if jobtastic_cache_setting:
            backend, url = get_backend_by_url(jobtastic_cache_setting)
            backend = backend(app=app, url=url)
        else:
            backend = app.backend
        if isinstance(backend, CacheBackend):
            return WrappedCache(MemcachedCache(backend.client))
        elif isinstance(backend, RedisBackend):
            return WrappedCache(RedisCache(backend.client))
    except ImportError:
        pass

    # Give up
    raise RuntimeError('Cannot find a suitable cache for Jobtastic')
