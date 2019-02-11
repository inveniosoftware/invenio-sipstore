# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2017-2019 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Proxy definitions."""

from __future__ import absolute_import, print_function

from flask import current_app
from werkzeug.local import LocalProxy

current_sipstore = LocalProxy(
    lambda: current_app.extensions['invenio-sipstore'])
"""Helper proxy to access the SIPStore state object."""
