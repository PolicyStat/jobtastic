import string
import random

from jobtastic import JobtasticTask

leaky_global = []


class BaseMemLeakyTask(JobtasticTask):
    """
    This task leaks memory like crazy, by adding things to `leaky_global`.
    """
    significant_kwargs = [
        ('bloat_factor', str),
    ]
    herd_avoidance_timeout = 0

    def calculate_result(self, bloat_factor, **kwargs):
        """
        Let's bloat our thing!
        """
        global leaky_global

        for _ in xrange(bloat_factor):
            # 1 million bytes for a MB
            new_str = u'X' * 1000000
            # Add something new to it so python can't just point to the same
            # memory location
            new_str += random.choice(string.letters)
            leaky_global.append(new_str)

        return bloat_factor


class MemLeakyTask(BaseMemLeakyTask):
    memleak_threshold = 10


class MemLeakyDisabledWarningTask(BaseMemLeakyTask):
    memleak_threshold = -1


class MemLeakyDefaultedTask(BaseMemLeakyTask):
    pass
