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

import json
import tempfile
import uuid
from shutil import rmtree

from invenio_accounts.testutils import create_test_user
from invenio_files_rest.models import Bucket, Location, ObjectVersion
from invenio_pidstore.models import PersistentIdentifier, PIDStatus
from invenio_records_files.api import Record
from invenio_records_files.models import RecordsBuckets
from six import BytesIO

from invenio_sipstore.api import SIP, RecordSIP
from invenio_sipstore.models import SIP as SIP_
from invenio_sipstore.models import RecordSIP as RecordSIP_
from invenio_sipstore.models import SIPFile, SIPMetadata, SIPMetadataType


def test_SIP(db):
    """Test SIP API class."""
    user = create_test_user('test@example.org')
    agent = {'email': 'user@invenio.org', 'ip_address': '1.1.1.1'}
    # we create a SIP model
    sip = SIP_.create(user_id=user.id, agent=agent)
    db.session.commit()
    # We create an API SIP on top of it
    api_sip = SIP(sip)
    assert api_sip.model is sip
    assert api_sip.id == sip.id
    assert api_sip.user is user
    assert api_sip.agent == agent
    assert api_sip.archivable is True
    assert api_sip.archived is False
    api_sip.archived = True
    db.session.commit()
    assert api_sip.archived is True
    assert sip.archived is True
    # test of the get method
    api_sip2 = SIP.get_sip(sip.id)
    assert api_sip2.id == api_sip.id


def test_SIP_files(db):
    """Test the files methods of API SIP."""
    # we create a SIP model
    sip = SIP_.create()
    db.session.commit()
    # We create an API SIP on top of it
    api_sip = SIP(sip)
    assert len(api_sip.files) == 0
    # we setup a file storage
    tmppath = tempfile.mkdtemp()
    db.session.add(Location(name='default', uri=tmppath, default=True))
    db.session.commit()
    # we create a file
    content = b'test lol\n'
    bucket = Bucket.create()
    obj = ObjectVersion.create(bucket, 'test.txt', stream=BytesIO(content))
    db.session.commit()
    # we attach it to the SIP
    sf = api_sip.attach_file(obj)
    db.session.commit()
    assert len(api_sip.files) == 1
    assert api_sip.files[0].filepath == 'test.txt'
    assert sip.sip_files[0].filepath == 'test.txt'
    # finalization
    rmtree(tmppath)


def test_SIP_metadata(db):
    """Test the metadata methods of API SIP."""
    # we create a SIP model
    sip = SIP_.create()
    mtype = SIPMetadataType(title='JSON Test', name='json-test',
                            format='json', schema='url')
    db.session.add(mtype)
    db.session.commit()
    # We create an API SIP on top of it
    api_sip = SIP(sip)
    assert len(api_sip.metadata) == 0
    # we create a dummy metadata
    metadata = json.dumps({'this': 'is', 'not': 'sparta'})
    # we attach it to the SIP
    sm = api_sip.attach_metadata('json-test', metadata)
    db.session.commit()
    assert len(api_sip.metadata) == 1
    assert api_sip.metadata[0].type.format == 'json'
    assert api_sip.metadata[0].content == metadata
    assert sip.sip_metadata[0].content == metadata


def test_SIP_build_agent_info(app, mocker):
    """Test SIP._build_agent_info static method."""
    # with no information, we get an empty dict
    agent = SIP._build_agent_info()
    assert agent == {}
    # we mock flask function to give more info
    mocker.patch('invenio_sipstore.api.has_request_context',
                 return_value=True, autospec=True)
    mock_request = mocker.patch('invenio_sipstore.api.request')
    type(mock_request).remote_addr = mocker.PropertyMock(
        return_value="localhost")
    mock_current_user = mocker.patch('invenio_sipstore.api.current_user')
    type(mock_current_user).is_authenticated = mocker.PropertyMock(
        return_value=True)
    type(mock_current_user).email = mocker.PropertyMock(
        return_value='test@invenioso.org')
    agent = SIP._build_agent_info()
    assert agent == {
        'ip_address': 'localhost',
        'email': 'test@invenioso.org'
    }


def test_SIP_create(app, db, mocker):
    """Test the create method from SIP API."""
    # we setup a file storage
    tmppath = tempfile.mkdtemp()
    db.session.add(Location(name='default', uri=tmppath, default=True))
    db.session.commit()
    # we create a file
    content = b'test lol\n'
    bucket = Bucket.create()
    obj = ObjectVersion.create(bucket, 'test.txt', stream=BytesIO(content))
    db.session.commit()
    files = [obj]
    # setup metadata
    mjson = SIPMetadataType(title='JSON Test', name='json-test',
                            format='json', schema='url')
    marcxml = SIPMetadataType(title='MARC XML Test', name='marcxml-test',
                              format='xml', schema='uri')
    db.session.add(mjson)
    db.session.add(marcxml)
    metadata = {
        'json-test': json.dumps({'this': 'is', 'not': 'sparta'}),
        'marcxml-test': '<record></record>'
    }
    # Let's create a SIP
    user = create_test_user('test@example.org')
    agent = {'email': 'user@invenio.org', 'ip_address': '1.1.1.1'}
    sip = SIP.create(True, files=files, metadata=metadata, user_id=user.id,
                     agent=agent)
    db.session.commit()
    assert SIP_.query.count() == 1
    assert len(sip.files) == 1
    assert len(sip.metadata) == 2
    assert SIPFile.query.count() == 1
    assert SIPMetadata.query.count() == 2
    assert sip.user.id == user.id
    assert sip.agent == agent
    # we mock the user and the agent to test if the creation works
    app.config['SIPSTORE_AGENT_JSONSCHEMA_ENABLED'] = False
    mock_current_user = mocker.patch('invenio_sipstore.api.current_user')
    type(mock_current_user).is_anonymous = mocker.PropertyMock(
        return_value=True)
    sip = SIP.create(True, files=files, metadata=metadata)
    assert sip.model.user_id is None
    assert sip.user is None
    assert sip.agent == {}
    # finalization
    rmtree(tmppath)


def test_RecordSIP(db):
    """Test RecordSIP API class."""
    user = create_test_user('test@example.org')
    agent = {'email': 'user@invenio.org', 'ip_address': '1.1.1.1'}
    # we create a record
    recid = uuid.uuid4()
    pid = PersistentIdentifier.create(
        'recid',
        '1337',
        object_type='rec',
        object_uuid=recid,
        status=PIDStatus.REGISTERED)
    title = {'title': 'record test'}
    record = Record.create(title, recid)
    # we create the models
    sip = SIP.create(True, user_id=user.id, agent=agent)
    recordsip = RecordSIP_(sip_id=sip.id, pid_id=pid.id)
    db.session.commit()
    # We create an API SIP on top of it
    api_recordsip = RecordSIP(recordsip, sip)
    assert api_recordsip.model is recordsip
    assert api_recordsip.sip.id == sip.id


def test_RecordSIP_create(db, mocker):
    """Test create method from the API class RecordSIP."""
    # we setup a file storage
    tmppath = tempfile.mkdtemp()
    db.session.add(Location(name='default', uri=tmppath, default=True))
    # setup metadata
    mtype = SIPMetadataType(title='JSON Test', name='json-test',
                            format='json', schema='url://to/schema')
    db.session.add(mtype)
    db.session.commit()
    # first we create a record
    recid = uuid.uuid4()
    pid = PersistentIdentifier.create(
        'recid',
        '1337',
        object_type='rec',
        object_uuid=recid,
        status=PIDStatus.REGISTERED)
    mocker.patch('invenio_records.api.RecordBase.validate',
                 return_value=True, autospec=True)
    record = Record.create(
        {'title': 'record test', '$schema': 'url://to/schema'},
        recid)
    # we add a file to the record
    bucket = Bucket.create()
    content = b'Test file\n'
    RecordsBuckets.create(record=record.model, bucket=bucket)
    record.files['test.txt'] = BytesIO(content)
    db.session.commit()
    # Let's create a SIP
    user = create_test_user('test@example.org')
    agent = {'email': 'user@invenio.org', 'ip_address': '1.1.1.1'}
    rsip = RecordSIP.create(pid, record, True, user_id=user.id, agent=agent)
    db.session.commit()
    # test!
    assert RecordSIP_.query.count() == 1
    assert SIP_.query.count() == 1
    assert SIPFile.query.count() == 1
    assert SIPMetadata.query.count() == 1
    assert len(rsip.sip.files) == 1
    assert len(rsip.sip.metadata) == 1
    metadata = rsip.sip.metadata[0]
    assert metadata.type.format == 'json'
    assert '"title": "record test"' in metadata.content
    assert rsip.sip.archivable is True
    # we try with no files
    rsip = RecordSIP.create(pid, record, True, create_sip_files=False,
                            user_id=user.id, agent=agent)
    assert SIPFile.query.count() == 1
    assert SIPMetadata.query.count() == 2
    assert len(rsip.sip.files) == 0
    assert len(rsip.sip.metadata) == 1
    # finalization
    rmtree(tmppath)
