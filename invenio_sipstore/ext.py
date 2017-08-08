# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016, 2017 CERN.
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

"""Submission Information Package store for Invenio."""

from __future__ import absolute_import, print_function

from invenio_files_rest.models import Location
from werkzeug.utils import cached_property

from . import config
from .utils import load_or_import_from_config


class _InvenioSIPStoreState(object):
    """Invenio SIPStore state."""

    def __init__(self, app):
        """Initialize state."""
        self.app = app

    @cached_property
    def storage_factory(self):
        """Load default storage factory."""
        return load_or_import_from_config(
            'SIPSTORE_FILE_STORAGE_FACTORY', app=self.app
        )

    @cached_property
    def archive_location(self):
        """Return the archive location URI.

        :rtype: str
        :return: URI to the archive root.
        """
        name = self.app.config['SIPSTORE_ARCHIVER_LOCATION_NAME']
        return Location.query.filter_by(name=name).one().uri

    @cached_property
    def archive_path_builder(self):
        return load_or_import_from_config(
            'SIPSTORE_ARCHIVER_DIRECTORY_BUILDER', app=self.app
        )

    @cached_property
    def sipmetadata_name_formatter(self):
        return load_or_import_from_config(
            'SIPSTORE_ARCHIVER_SIPMETADATA_NAME_FORMATTER', app=self.app
        )

    @cached_property
    def sipfile_name_formatter(self):
        return load_or_import_from_config(
            'SIPSTORE_ARCHIVER_SIPFILE_NAME_FORMATTER', app=self.app
        )


class InvenioSIPStore(object):
    """Invenio-SIPStore extension."""

    def __init__(self, app=None):
        """Extension initialization."""
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Flask application initialization."""
        self.init_config(app)
        app.extensions['invenio-sipstore'] = _InvenioSIPStoreState(app)

    def init_config(self, app):
        """Initialize configuration."""
        for k in dir(config):
            if k.startswith('SIPSTORE_'):
                app.config.setdefault(k, getattr(config, k))
