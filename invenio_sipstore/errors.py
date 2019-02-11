# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016-2019 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Errors for Submission Information Packages."""

from __future__ import absolute_import, print_function


class SIPError(Exception):
    """Base class for SIPStore errors."""


class SIPUserDoesNotExist(SIPError):
    """User ID for SIP does not exist."""

    def __init__(self, user_id, *args, **kwargs):
        """Initialize exception."""
        self.user_id = user_id
        super(SIPUserDoesNotExist, self).__init__(*args, **kwargs)
