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

from __future__ import absolute_import, print_function, unicode_literals

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
from six import BytesIO, b
from sqlalchemy_utils.functions import create_database, database_exists, \
    drop_database

from invenio_sipstore import InvenioSIPStore
from invenio_sipstore.api import SIP as SIPApi
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
        SIPSTORE_ARCHIVER_METADATA_TYPES=['json-test', 'marcxml-test']
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
def locations(db, instance_path):
    """File system location."""
    default = Location(
        name='default',
        uri=instance_path,
        default=True
    )
    archive = Location(
        name='archive',
        uri=os.path.join(instance_path, 'archive'),
        default=False
    )
    db.session.add(default)
    db.session.add(archive)
    db.session.commit()
    return dict((loc.name, loc) for loc in [default, archive])


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
        title='Record MARCXML Metadata',
        name='marcxml-test',
        format='xml')
    # The type 'txt-test' is intentionally ommited from the configuration
    # (SIPSTORE_ARCHIVER_METADATA_TYPES). It should not be archived in any of
    # the tests.
    txt_type = SIPMetadataType(
        title='Raw Text Metadata',
        name='txt-test',
        format='txt')

    db.session.add(bagit_type)
    db.session.add(json_type)
    db.session.add(xml_type)
    db.session.add(txt_type)
    db.session.commit()
    types = dict((t.name, t) for t in [bagit_type, json_type, xml_type])

    return types


@pytest.fixture()
def sips(db, locations, sip_metadata_types):
    """Fixture for the SIP objects sharing multiple files.

    Three SIPs are sharing three files in the following way:
    SIP-1: File1
    SIP-2: File1, File2
    SIP-3: File2(renamed on SIPFile, but same FileInstance), File3
    """
    sip1 = SIP.create()
    sip1api = SIPApi(sip1)
    sip1api.attach_metadata('marcxml-test', '<p>XML 1</p>')
    sip1api.attach_metadata('json-test', '{"title": "JSON 1"}')
    # Metadata 'txt-test', although attached should not be archived
    # (see conftest configuration)
    sip1api.attach_metadata('txt-test', 'Title: TXT 1')
    file1 = FileInstance.create()
    file1.set_contents(BytesIO(b('test')),
                       default_location=locations['default'].uri)
    sip1file1 = SIPFile(sip_id=sip1.id, filepath="foobar.txt",
                        file_id=file1.id)

    db_.session.add(sip1file1)

    sip2 = SIP.create()
    sip2api = SIPApi(sip2)
    sip2api.attach_metadata('marcxml-test', '<p>XML 2</p>')
    sip2api.attach_metadata('json-test', '{"title": "JSON 2"}')
    file2 = FileInstance.create()
    file2.set_contents(BytesIO(b'test-second'),
                       default_location=locations['default'].uri)
    sip2file1 = SIPFile(sip_id=sip2.id, filepath="foobar.txt",
                        file_id=file1.id)
    sip2file2 = SIPFile(sip_id=sip2.id, filepath="foobar2.txt",
                        file_id=file2.id)

    db_.session.add(sip2file1)
    db_.session.add(sip2file2)

    sip3 = SIP.create()
    sip3api = SIPApi(sip3)
    sip3api.attach_metadata('marcxml-test', '<p>XML 3</p>')
    sip3api.attach_metadata('json-test', '{"title": "JSON 3"}')
    file3 = FileInstance.create()
    file3.set_contents(BytesIO(b'test-third'),
                       default_location=locations['default'].uri)
    sip3file2 = SIPFile(sip_id=sip3.id, filepath="foobar2-renamed.txt",
                        file_id=file2.id)
    sip3file3 = SIPFile(sip_id=sip3.id, filepath="foobar3.txt",
                        file_id=file3.id)

    db_.session.add(sip3file2)
    db_.session.add(sip3file3)

    # A SIP with naughty filenames
    sip4 = SIP.create()
    sip4api = SIPApi(sip4)
    sip4api.attach_metadata('marcxml-test', '<p>XML 4 żółć</p>')
    sip4api.attach_metadata('json-test', '{"title": "JSON 4 żółć"}')
    file4 = FileInstance.create()
    file4.set_contents(BytesIO('test-fourth żółć'.encode('utf-8')),
                       default_location=locations['default'].uri)
    file5 = FileInstance.create()
    file5.set_contents(BytesIO('test-fifth ąęćźə'.encode('utf-8')),
                       default_location=locations['default'].uri)

    file6 = FileInstance.create()
    file6.set_contents(BytesIO('test-sixth π'.encode('utf-8')),
                       default_location=locations['default'].uri)
    sip5file4 = SIPFile(sip_id=sip4.id, filepath="../../foobar.txt",
                        file_id=file4.id)

    sip5file5 = SIPFile(sip_id=sip4.id,
                        filepath="http://maliciouswebsite.com/hack.js",
                        file_id=file5.id)

    sip5file6 = SIPFile(sip_id=sip4.id,
                        filepath="łóżźćąę.dat",
                        file_id=file6.id)

    db_.session.add(sip5file4)
    db_.session.add(sip5file5)
    db_.session.add(sip5file6)

    db_.session.commit()
    return [sip1api, sip2api, sip3api, sip4api]


@pytest.yield_fixture()
def archive_fs(locations):
    """Fixture to check the BagIt file generation."""
    archive_path = locations['archive'].uri
    fs = opener.opendir(archive_path, writeable=False, create_dir=True)
    yield fs
    for d in fs.listdir():
        fs.removedir(d, force=True)


@pytest.yield_fixture()
def secure_sipfile_name_formatter(app):
    """Temporarily change the default name formatter for SIPFiles."""
    fmt = app.config['SIPSTORE_ARCHIVER_SIPFILE_NAME_FORMATTER']
    app.config['SIPSTORE_ARCHIVER_SIPFILE_NAME_FORMATTER'] = \
        'invenio_sipstore.archivers.utils.secure_sipfile_name_formatter'
    yield
    app.config['SIPSTORE_ARCHIVER_SIPFILE_NAME_FORMATTER'] = fmt


@pytest.yield_fixture()
def custom_sipmetadata_name_formatter(app):
    """Temporarily change the default name formatter for SIPMetadata files."""
    fmt = app.config['SIPSTORE_ARCHIVER_SIPMETADATA_NAME_FORMATTER']

    app.config['SIPSTORE_ARCHIVER_SIPMETADATA_NAME_FORMATTER'] = \
        lambda sm: '{0}-metadata.{1}'.format(sm.type.name, sm.type.format)
    yield
    app.config['SIPSTORE_ARCHIVER_SIPMETADATA_NAME_FORMATTER'] = fmt
