# -*- coding: utf-8 -*-

import codecs
import os
import sys

from setuptools import setup, find_packages, Command

long_description = codecs.open("README.md", "r", "utf-8").read()

CLASSIFIERS = [
    'Development Status :: 4 - Beta',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Topic :: System :: Distributed Computing',
    'Topic :: Software Development :: Object Brokering',
    'Programming Language :: Python',
    'Programming Language :: Python :: 2.6',
    'Programming Language :: Python :: 2.7',
    'Operating System :: OS Independent',
    'Operating System :: POSIX',
    'Operating System :: Microsoft :: Windows',
    'Operating System :: MacOS :: MacOS X',
    'Framework :: Django',
]

NAME = 'jobtastic'

# Distribution Meta stuff because we can't just import jobtastic
# Mostly cribbed fro Celery's setup.py

import re

# Standard ``__foo__ = 'bar'`` pairs.
re_meta = re.compile(r'__(\w+?)__\s*=\s*(.*)')
# VERSION tuple
re_vers = re.compile(r'VERSION\s*=\s*\((.*?)\)')
# Module docstring
re_doc = re.compile(r'^"""(.+?)"""')
# We don't need the quotes
rq = lambda s: s.strip("\"'")


def add_default(m):
    """
    Get standard ``__foo__ = 'bar'`` pairs as a (foo, bar) tuple.
    """
    attr_name, attr_value = m.groups()
    return ((attr_name, rq(attr_value)), )


def add_version(m):
    v = list(map(rq, m.groups()[0].split(', ')))
    return (('VERSION', '.'.join(v[0:3]) + ''.join(v[3:])), )


def add_doc(m):
    """
    Grab the module docstring
    """
    return (('doc', m.groups()[0]), )

pats = {
    re_meta: add_default,
    re_vers: add_version,
    re_doc: add_doc,
}

here = os.path.abspath(os.path.dirname(__file__))
meta_fh = open(os.path.join(here, 'jobtastic/__init__.py'))

# Parse out the package meta information from the __init__ using *shudder*
# regexes
meta = {}
try:
    for line in meta_fh:
        if line.strip() == '# -eof meta-':
            break
        for pattern, handler in pats.items():
            m = pattern.match(line.strip())
            if m:
                meta.update(handler(m))
finally:
    meta_fh.close()

# -*- Installation Requires -*-


def strip_comments(l):
    return l.split('#', 1)[0].strip()


def reqs(*f):
    return list(filter(None, [strip_comments(l) for l in open(
        os.path.join(os.getcwd(), 'requirements', *f)).readlines()]))

install_requires = reqs('default.txt')
tests_require = reqs('tests.txt')

# -*- Test Runners -*-


class RunDjangoTests(Command):
    description = 'Run the django test suite from the tests dir.'
    user_options = []
    extra_env = {}
    extra_args = []

    def run(self):
        for env_name, env_value in self.extra_env.items():
            os.environ[env_name] = str(env_value)

        this_dir = os.getcwd()
        testproj_dir = os.path.join(this_dir, 'test_projects')
        django_testproj_dir = os.path.join(testproj_dir, 'django')
        os.chdir(django_testproj_dir)
        sys.path.append(django_testproj_dir)

        os.environ['DJANGO_SETTINGS_MODULE'] = os.environ.get(
            'DJANGO_SETTINGS_MODULE',
            'testproj.settings',
        )

        from django.core.management import execute_from_command_line

        modified_args = [__file__, 'test'] + self.extra_args
        execute_from_command_line(modified_args)

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass


setup(
    name=NAME,
    version=meta['VERSION'],
    description=meta['doc'],
    author=meta['author'],
    author_email=meta['contact'],
    url=meta['homepage'],
    long_description=long_description,
    packages=find_packages(),
    license='BSD',
    platforms=['any'],
    classifiers=CLASSIFIERS,
    cmdclass={
        'test': RunDjangoTests,
    },
    install_requires=install_requires,
    tests_require=tests_require,
)
