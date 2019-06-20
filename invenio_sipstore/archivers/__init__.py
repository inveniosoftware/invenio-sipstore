# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016-2019 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Archivers for SIPStore module.

An archiver is an controller that can serialize a SIP to disk according to a
specific format. Currently Invenio-SIPStore comes with a BagIt archiver that
can write packages according to "The BagIt File Packaging Format (V0.97)".

New formats can be implemented by subclassing
:py:class:`~.base_archiver.BaseArchiver`.
"""

from __future__ import absolute_import, print_function

from .bagit_archiver import BagItArchiver
from .base_archiver import BaseArchiver
