# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2017-2019 CERN.
# Copyright (C) 2024 TU Wien.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Proxy definitions."""

from flask import current_app
from werkzeug.local import LocalProxy

current_sipstore = LocalProxy(lambda: current_app.extensions["invenio-sipstore"])
"""Helper proxy to access the SIPStore state object."""
