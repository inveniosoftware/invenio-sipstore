# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016-2019 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Submission Information Package store for Invenio."""

import os

from setuptools import find_packages, setup

readme = open('README.rst').read()
history = open('CHANGES.rst').read()

tests_require = [
    'check-manifest>=0.25',
    'coverage>=4.0',
    'invenio-records-files>=1.0.0a11',
    'isort>=4.3.4',
    'pydocstyle>=1.0.0',
    'pytest-cov>=1.8.0',
    'pytest-mock>=1.6.0',
    'pytest-pep8>=1.0.6',
    'pytest>=2.8.0',
    'more-itertools<=5.0.0'  # dropped python 2.7 support in 6.x
]

extras_require = {
    'admin': [
        'Flask-Admin>=1.3.0',
    ],
    'docs': [
        'Sphinx>=1.4.2',
    ],
    'tests': tests_require,
}

extras_require['all'] = []
for reqs in extras_require.values():
    extras_require['all'].extend(reqs)

setup_requires = [
    'pytest-runner>=2.6.2',
]

install_requires = [
    'Flask>=0.11.1',
    'invenio-db>=1.0.0',
    'invenio-accounts>=1.0.0',
    'invenio-pidstore>=1.0.0',
    'invenio-jsonschemas>=1.0.0',
    'invenio-files-rest>=1.0.0a23',
    'jsonschema>=2.6.0',
]

packages = find_packages()


# Get the version string. Cannot be done with import!
g = {}
with open(os.path.join('invenio_sipstore', 'version.py'), 'rt') as fp:
    exec(fp.read(), g)
    version = g['__version__']

setup(
    name='invenio-sipstore',
    version=version,
    description=__doc__,
    long_description=readme + '\n\n' + history,
    keywords='invenio submission information packages',
    license='MIT',
    author='CERN',
    author_email='info@inveniosoftware.org',
    url='https://github.com/inveniosoftware/invenio-sipstore',
    packages=packages,
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    entry_points={
        'invenio_db.models': [
            'invenio_sipstore = invenio_sipstore.models',
        ],
        'invenio_db.alembic': [
            'invenio_sipstore = invenio_sipstore:alembic',
        ],
        'invenio_base.apps': [
            'invenio_sipstore = invenio_sipstore:InvenioSIPStore',
        ],
        'invenio_base.api_apps': [
            'invenio_sipstore = invenio_sipstore:InvenioSIPStore',
        ],
        'invenio_jsonschemas.schemas': [
            'sipstore = invenio_sipstore.jsonschemas',
        ],
        'invenio_admin.views': [
            'invenio_sipstore_sip = invenio_sipstore.admin:sip_adminview',
            'invenio_sipstore_sipfile = '
            'invenio_sipstore.admin:sipfile_adminview',
            'invenio_sipstore_sipmetadata = '
            'invenio_sipstore.admin:sipmetadata_adminview',
            'invenio_sipstore_sipmetadatatype = '
            'invenio_sipstore.admin:sipmetadatatype_adminview',
            'invenio_sipstore_recordsip = '
            'invenio_sipstore.admin:recordsip_adminview',
        ]
    },
    extras_require=extras_require,
    install_requires=install_requires,
    setup_requires=setup_requires,
    tests_require=tests_require,
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: CPython',
        'Development Status :: 5 - Production/Stable',
    ],
)
