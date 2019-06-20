# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016-2019 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Submission Information Package store for Invenio."""

from __future__ import absolute_import, print_function

from .ext import InvenioSIPStore
from .proxies import current_sipstore
from .version import __version__

__all__ = ('__version__', 'current_sipstore', 'InvenioSIPStore')
