# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016 CERN.
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

"""Background tasks for sipstore."""

from __future__ import absolute_import, print_function

from datetime import datetime

from celery import shared_task
from flask import current_app
from fs.opener import opener
from invenio_db import db

from .archivers import BagItArchiver
from .models import SIP


@shared_task
def archive_sip(sip_id, location=None):
    """Celery task to create a bagit file from a sip package."""
    sip = SIP.query.get(sip_id)

    archival_start = datetime.now()

    # Calculate the path in case that location is not set.
    location = location or BagItArchiver.get_default_archive_location(
        sip, current_app.config['SIPSTORE_ARCHIVE_BASEPATH'], archival_start)

    # Create the FileSystem where the BagIt file creation will be done.
    fs, path = opener.parse(location, writeable=True, create_dir=True)
    fs = fs.opendir(path)

    # Back up the data inside the file system.
    BagItArchiver(fs).archive(sip, lambda c, t: None)

    # Update the database.
    sip.archived_at = archival_start
    sip.archive_uri = location
    db.session.commit()
