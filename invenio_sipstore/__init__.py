# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016-2019 CERN.
# Copyright (C) 2024 TU Wien.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Submission Information Package store for Invenio."""

from .ext import InvenioSIPStore
from .proxies import current_sipstore

__version__ = "1.0.0a7"

__all__ = ("__version__", "current_sipstore", "InvenioSIPStore")
