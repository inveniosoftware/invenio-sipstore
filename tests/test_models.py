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


"""Module tests."""

from __future__ import absolute_import, print_function

import pytest
from invenio_accounts.testutils import create_test_user
from invenio_jsonschemas.errors import JSONSchemaNotFound
from invenio_pidstore.models import PersistentIdentifier
from jsonschema.exceptions import ValidationError

from invenio_sipstore.errors import SIPUserDoesNotExist
from invenio_sipstore.models import SIP, RecordSIP, SIPFile, SIPMetadata, \
    SIPMetadataType


def test_sip_model(db):
    """Test the SIP model."""
    user1 = create_test_user('test@example.org')

    # Valid agent JSON
    agent1 = {'email': 'user@invenio.org', 'ip_address': '1.1.1.1'}

    # Invalid agent JSON
    agent2 = {
        'email': ['should', 'not', 'be', 'a', 'list'],
        'ip_address': {'definitely': 'not', 'a': 'dict'},
    }
    # Agent JSON with wrong schema
    agent3 = {
        'email': 'user@invenio.org',
        'ip_address': '1.1.1.1',
        '$schema': 'http://incorrect/agent/schema.json',
    }
    sip1 = SIP.create(user_id=user1.id, agent=agent1)
    assert sip1.user == user1

    SIP.create()
    SIP.create(user_id=user1.id, agent=agent1)
    assert SIP.query.count() == 3

    pytest.raises(ValidationError, SIP.create, agent=agent2)
    pytest.raises(SIPUserDoesNotExist, SIP.create, user_id=5)
    pytest.raises(JSONSchemaNotFound, SIP.create, agent=agent3)
    db.session.commit()


def test_sip_file_model(app, db, sip_with_file):
    """Test the SIPFile model."""
    assert SIP.query.count() == 1
    assert SIPFile.query.count() == 1
    app.config['SIPSTORE_FILEPATH_MAX_LEN'] = 15
    with pytest.raises(ValueError) as excinfo:
        sipfile2 = SIPFile(sip_id=sip_with_file.id,
                           filepath="way too long file name.zip",
                           file_id=sip_with_file.sip_files[0].file_id)
    assert 'Filepath too long' in str(excinfo.value)


def test_sip_file_storage_location(db, sip_with_file):
    """Test the storage_location SIPFile member."""
    assert sip_with_file.sip_files[0].filepath == 'foobar.txt'
    with open(sip_with_file.sip_files[0].storage_location, "rb") as f:
        assert f.read() == b'test'


def test_sip_metadata_model(db):
    """Test the SIPMetadata model."""
    sip1 = SIP.create()
    mtype = SIPMetadataType(title='JSON Test', name='json-test',
                            format='json', schema='url')
    db.session.add(mtype)
    metadata1 = '{"title": "great book"}'
    sipmetadata = SIPMetadata(sip_id=sip1.id, content=metadata1,
                              type=mtype)
    db.session.add(sipmetadata)
    db.session.commit()
    assert SIP.query.count() == 1
    assert SIPMetadataType.query.count() == 1
    assert SIPMetadata.query.count() == 1
    sipmetadata = SIPMetadata.query.one()
    assert sipmetadata.content == metadata1
    assert sipmetadata.type.format == 'json'
    assert sipmetadata.sip.id == sip1.id


def test_sip_metadatatype_model(db):
    """Test the SIPMetadata model."""
    sip1 = SIP.create()
    mtype = SIPMetadataType(title='JSON Test', name='json-test',
                            format='json', schema='url')
    db.session.add(mtype)
    db.session.commit()
    assert SIP.query.count() == 1
    assert SIPMetadataType.query.count() == 1
    sipmetadatatype = SIPMetadataType.get(mtype.id)
    assert sipmetadatatype.title == 'JSON Test'
    assert sipmetadatatype.format == 'json'
    assert sipmetadatatype.name == 'json-test'
    assert sipmetadatatype.schema == 'url'


def test_record_sip_model(db):
    """Test the RecordSIP model."""
    sip1 = SIP.create()
    db.session.commit()
    pid1 = PersistentIdentifier.create('recid', '12345')

    rsip1 = RecordSIP(sip_id=sip1.id, pid_id=pid1.id)
    db.session.add(rsip1)
    db.session.commit()
    assert RecordSIP.query.count() == 1
