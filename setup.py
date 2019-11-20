# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open('README.rst') as f:
    README = f.read()

with open('LICENSE') as f:
    LICENSE = f.read()

with open('pyotrs/version.py') as f:
    __version__ = ''
    exec(f.read())  # set __version__

setup(
    name='PyOTRS',
    version=__version__,
    author='Robert Habermann',
    author_email='mail@rhab.de',
    maintainer='Robert Habermann',
    url='https://gitlab.com/rhab/PyOTRS',
    description='Python wrapper for OTRS (using REST API)',
    long_description=README,
    packages=find_packages(exclude=('tests', 'docs')),
    include_package_data=True,
    zip_safe=False,
    license=LICENSE,
    install_requires=[
        'requests', 'click', 'colorama',
    ],
    entry_points='''
        [console_scripts]
        pyotrs=cli.PyOTRS:cli
    ''',
    test_suite='unittest2.collector',
    tests_require=['tox', 'coverage', 'unittest2', 'mock', 'responses'],
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        'Environment :: Console',
        'Environment :: Web Environment',

        'Framework :: Pytest',
        'Framework :: Sphinx',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',

        'License :: OSI Approved :: MIT License',

        'Operating System :: POSIX :: Linux',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',

        'Topic :: Documentation :: Sphinx',
    ],
)
