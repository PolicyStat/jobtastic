"""Make your user-facing Celery jobs totally awesomer"""

VERSION = (0, 3, 1, '')
__version__ = '.'.join(map(str, VERSION[0:3])) + ''.join(VERSION[3:])
__author__ = 'Wes Winham'
__contact__ = 'winhamwr@gmail.com'
__homepage__ = 'http://policystat.github.com/jobtastic'
__docformat__ = 'markdown'

__all__ = (
    'JobtasticTask',
    '__version__',
)

# -eof meta-

# Reserved for default settings
DEFAULT_RESULT_BACKEND = 'cache'
DEFAULT_CACHE_BACKEND = 'memcached://127.0.0.1:11211/'

from .task import JobtasticTask  # NOQA
