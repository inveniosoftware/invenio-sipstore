# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2017-2019 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Signals for the module."""

from blinker import Namespace

_signals = Namespace()

sipstore_created = _signals.signal('sipstore_created')
"""Signal sent each time a SIP has been created.

Send the SIP as a parameter: :py:class:`invenio_sipstore.api.SIP`

Example subscriber

.. code-block:: python

    def listener(sender, *args, **kwargs):
        # sender is the SIP being archived
        for f in sender.files:
            print(f.filepath)

    from invenio_sipstore.signals import sipstore_created
    sipstore_created.connect(listener)
"""

sipstore_archiver_status = _signals.signal('sipstore_archiver_status')
"""Signal sent during the archiving processing.

Sends a dict with the following information inside:
- total_files: the total number of files to copy
- total_size: the total size to copy
- copied_files: the number of copied files
- copied_size: the size copied
- current_filename: the name of the last copied file
- current_filesize: the size of the last copied file
"""
