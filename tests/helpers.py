# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2017-2019 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.


"""Pytest helpers."""

from __future__ import absolute_import, print_function


def get_file(filename, result):
    """Get a file by its filename from the results list."""
    return next((f for f in result if f['filename'] == filename), None)
