# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2017 CERN.
#
# Invenio is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

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

Sends a dict with the following informations inside:
- total_files: the total number of files to copy
- total_size: the total size to copy
- copied_files: the number of copied files
- copied_size: the size copied
- current_filename: the name of the last copied file
- current_filesize: the size of the last copied file

See :py:func:`invenio_sipstore.archivers.BaseArchiver._copy_files`.
"""
