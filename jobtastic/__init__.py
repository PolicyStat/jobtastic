"""Make your user-facing Celery jobs totally awesomer"""

VERSION = (0, 2, 2, '')
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

from jobtastic.task import JobtasticTask
