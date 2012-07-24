# -*- coding: utf-8 -*-

import codecs

from setuptools import setup

long_description = codecs.open("README.md", "r", "utf-8").read()

CLASSIFIERS = [
    'Development Status :: 4 - Beta',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: BSD License',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Topic :: Software Development :: Libraries :: Python Modules',
    'Framework :: Django',
]

import jobtastic
setup(
    name='jobtastic',
    version=jobtastic.__version__,
    description=jobtastic.__doc__,
    author=jobtastic.__author__,
    author_email=jobtastic.__contact__,
    url=jobtastic.__homepage__,
    long_description=long_description,
    packages=['jobtastic'],
    license='BSD',
    platforms=['any'],
    classifiers=CLASSIFIERS,
    install_requires=[
        'celery>=2.5',
    ],
)
