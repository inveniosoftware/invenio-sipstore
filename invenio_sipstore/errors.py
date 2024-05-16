# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016-2019 CERN.
# Copyright (C) 2024 TU Wien.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Errors for Submission Information Packages."""


class SIPError(Exception):
    """Base class for SIPStore errors."""


class SIPUserDoesNotExist(SIPError):
    """User ID for SIP does not exist."""

    def __init__(self, user_id, *args, **kwargs):
        """Initialize exception."""
        self.user_id = user_id
        super().__init__(*args, **kwargs)
