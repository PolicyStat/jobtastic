import string
import random

from jobtastic import JobtasticTask

leaky_global = {}


class MemLeakyTask(JobtasticTask):
    """
    This task leaks memory like crazy, by adding things to `leaky_global`.
    """
    significant_kwargs = [
        ('bloat_factor', str),
    ]
    herd_avoidance_timeout = 0
    memory_growth_warning_trigger = 2

    def calculate_result(self, bloat_factor, **kwargs):
        """
        Let's bloat our thing!
        """
        global leaky_global

        if 'bloat' not in leaky_global:
            leaky_global['bloat'] = []

        for _ in xrange(bloat_factor):
            # 1 million bytes for a MB
            new_str = u'X' * 1000000
            # Add something new to it so python can't just point to the same
            # memory location
            new_str += random.choice(string.letters)
            leaky_global['bloat'].append(new_str)

        return bloat_factor
