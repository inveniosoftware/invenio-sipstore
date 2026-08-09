#!/usr/bin/env sh
# SPDX-FileCopyrightText: 2016-2019 CERN.
# SPDX-License-Identifier: MIT

pydocstyle invenio_sipstore && \
isort -rc -c -df **/*.py && \
sphinx-build -qnNW docs docs/_build/html && \
python setup.py test && \
sphinx-build -qnNW -b doctest docs docs/_build/doctest
