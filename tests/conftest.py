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


"""Pytest configuration."""

from __future__ import absolute_import, print_function

import os
import shutil
import tempfile

import pytest
from flask import Flask
from fs.opener import opener
from invenio_accounts import InvenioAccounts
from invenio_db import db as db_
from invenio_db import InvenioDB
from invenio_files_rest import InvenioFilesREST
from invenio_files_rest.models import FileInstance, Location
from invenio_jsonschemas import InvenioJSONSchemas
from six import BytesIO
from sqlalchemy_utils.functions import create_database, database_exists, \
    drop_database

from invenio_sipstore import InvenioSIPStore
from invenio_sipstore.archivers import BagItArchiver
from invenio_sipstore.models import SIP, SIPFile, SIPMetadataType


@pytest.yield_fixture(scope='session')
def instance_path():
    """Default instance path."""
    path = tempfile.mkdtemp()

    yield path

    shutil.rmtree(path)


@pytest.fixture()
def base_app(instance_path):
    """Flask application fixture."""
    app = Flask('testapp', instance_path=instance_path)
    app.config.update(
        TESTING=True,
        SECRET_KEY='CHANGE_ME',
        SECURITY_PASSWORD_SALT='CHANGE_ME',
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            'SQLALCHEMY_DATABASE_URI', 'sqlite:///test.db'),
    )
    InvenioSIPStore(app)
    return app


@pytest.yield_fixture()
def app(base_app):
    """Flask application fixture."""
    InvenioDB(base_app)
    InvenioAccounts(base_app)
    InvenioFilesREST(base_app)
    InvenioJSONSchemas(base_app)
    with base_app.app_context():
        yield base_app


@pytest.yield_fixture()
def db(app):
    """Setup database."""
    if not database_exists(str(db_.engine.url)):
        create_database(str(db_.engine.url))
    db_.create_all()
    yield db_
    db_.session.remove()
    db_.drop_all()
    drop_database(str(db_.engine.url))


@pytest.fixture()
def dummy_location(db, instance_path):
    """File system location."""
    loc = Location(
        name='testloc',
        uri=instance_path,
        default=True
    )
    db.session.add(loc)
    db.session.commit()
    return loc


@pytest.fixture()
def sip_metadata_types(db):
    """Add a SIP metadata type (internal use only) for BagIt."""
    bagit_type = SIPMetadataType(
        title='BagIt Archiver Metadata',
        name=BagItArchiver.bagit_metadata_type_name,
        format='json',
        )
    json_type = SIPMetadataType(
        title='Record JSON Metadata',
        name='json-test',
        format='json')

    xml_type = SIPMetadataType(
        title='Record XML Metadata',
        name='xml-test',
        format='xml')

    db.session.add(bagit_type)
    db.session.add(json_type)
    db.session.add(xml_type)
    db.session.commit()
    types = dict((t.name, t) for t in [bagit_type, json_type, xml_type])

    return types


@pytest.fixture()
def sip_with_file(dummy_location, db):
    """Test the SIPFile model."""
    sip = SIP.create()
    file = FileInstance.create()
    file.set_contents(BytesIO(b'test'), default_location=dummy_location.uri)
    sipfile = SIPFile(sip_id=sip.id, filepath="foobar.txt", file_id=file.id)

    db_.session.add(sipfile)
    db_.session.commit()
    return sip


@pytest.yield_fixture()
def tmp_archive_fs():
    """Fixture to check the BagIt file generation."""
    tmp_path = tempfile.mkdtemp()
    fs, path = opener.parse(tmp_path, writeable=True, create_dir=True)
    fs = fs.opendir(path)
    yield fs
    shutil.rmtree(tmp_path)
