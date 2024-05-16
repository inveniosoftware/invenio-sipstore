# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016-2019 CERN.
# Copyright (C) 2024 TU Wien.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.


"""Module tests."""

import json
import tempfile
from io import BytesIO
from shutil import rmtree

import pytest
from invenio_access.permissions import system_identity
from invenio_accounts.testutils import create_test_user
from invenio_files_rest.models import Bucket, Location, ObjectVersion
from invenio_rdm_records.proxies import current_rdm_records_service as records_service

from invenio_sipstore.api import SIP, RecordSIP, default_agent_info_builder
from invenio_sipstore.models import SIP as SIP_
from invenio_sipstore.models import RecordSIP as RecordSIP_
from invenio_sipstore.models import SIPFile, SIPMetadata, SIPMetadataType


@pytest.fixture()
def minimal_record(running_app):
    """Minimal record data as dict coming from the external world."""
    return {
        "pids": {},
        "access": {
            "record": "public",
            "files": "public",
        },
        "files": {
            "enabled": True,
        },
        "metadata": {
            "creators": [
                {
                    "person_or_org": {
                        "family_name": "Brown",
                        "given_name": "Troy",
                        "type": "personal",
                    }
                },
                {
                    "person_or_org": {
                        "name": "Troy Inc.",
                        "type": "organizational",
                    },
                },
            ],
            "publication_date": "2020-06-01",
            "publisher": "Acme Inc",
            "resource_type": {"id": "image-photo"},
            "title": "A Romans story",
        },
    }


def test_SIP(db):
    """Test SIP API class."""
    user = create_test_user("test@example.org")
    agent = {"email": "user@invenio.org", "ip_address": "1.1.1.1"}
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
    db.session.add(Location(name="default", uri=tmppath, default=True))
    db.session.commit()
    # we create a file
    content = b"test lol\n"
    bucket = Bucket.create()
    obj = ObjectVersion.create(bucket, "test.txt", stream=BytesIO(content))
    db.session.commit()
    # we attach it to the SIP
    api_sip.attach_file(obj)
    db.session.commit()
    assert len(api_sip.files) == 1
    assert api_sip.files[0].filepath == "test.txt"
    assert sip.sip_files[0].filepath == "test.txt"
    # finalization
    rmtree(tmppath)


def test_SIP_metadata(db):
    """Test the metadata methods of API SIP."""
    # we create a SIP model
    sip = SIP_.create()
    mtype = SIPMetadataType(
        title="JSON Test", name="json-test", format="json", schema="url"
    )
    db.session.add(mtype)
    db.session.commit()
    # We create an API SIP on top of it
    api_sip = SIP(sip)
    assert len(api_sip.metadata) == 0
    # we create a dummy metadata
    metadata = json.dumps({"this": "is", "not": "sparta"})
    # we attach it to the SIP
    api_sip.attach_metadata("json-test", metadata)
    db.session.commit()
    assert len(api_sip.metadata) == 1
    assert api_sip.metadata[0].type.format == "json"
    assert api_sip.metadata[0].content == metadata
    assert sip.sip_metadata[0].content == metadata


def test_SIP_default_agent_info_builder(app, mocker):
    """Test the default function for building agent info."""
    with app.test_request_context():
        # with no information, we get an empty dict
        agent = default_agent_info_builder()
        assert agent == {}
        # we mock flask function to give more info
        mocker.patch(
            "invenio_sipstore.api.has_request_context", return_value=True, autospec=True
        )
        mock_request = mocker.patch("invenio_sipstore.api.request")
        type(mock_request).remote_addr = mocker.PropertyMock(return_value="localhost")
        mock_current_user = mocker.patch("invenio_sipstore.api.current_user")
        type(mock_current_user).is_authenticated = mocker.PropertyMock(
            return_value=True
        )
        type(mock_current_user).email = mocker.PropertyMock(
            return_value="test@invenioso.org"
        )
        agent = default_agent_info_builder()
        assert agent == {"ip_address": "localhost", "email": "test@invenioso.org"}


def test_SIP_create(app, db, mocker):
    """Test the create method from SIP API."""
    # we setup a file storage
    tmppath = tempfile.mkdtemp()
    db.session.add(Location(name="default", uri=tmppath, default=True))
    db.session.commit()
    # we create a file
    content = b"test lol\n"
    bucket = Bucket.create()
    obj = ObjectVersion.create(bucket, "test.txt", stream=BytesIO(content))
    db.session.commit()
    files = [obj]
    # setup metadata
    mjson = SIPMetadataType(
        title="JSON Test", name="json-test", format="json", schema="url"
    )
    marcxml = SIPMetadataType(
        title="MARC XML Test", name="marcxml-test", format="xml", schema="uri"
    )
    db.session.add(mjson)
    db.session.add(marcxml)
    metadata = {
        "json-test": json.dumps({"this": "is", "not": "sparta"}),
        "marcxml-test": "<record></record>",
    }
    # Let's create a SIP
    user = create_test_user("test@example.org")
    agent = {"email": "user@invenio.org", "ip_address": "1.1.1.1"}
    sip = SIP.create(True, files=files, metadata=metadata, user_id=user.id, agent=agent)
    db.session.commit()
    assert SIP_.query.count() == 1
    assert len(sip.files) == 1
    assert len(sip.metadata) == 2
    assert SIPFile.query.count() == 1
    assert SIPMetadata.query.count() == 2
    assert sip.user.id == user.id
    assert sip.agent == agent
    # we mock the user and the agent to test if the creation works
    app.config["SIPSTORE_AGENT_JSONSCHEMA_ENABLED"] = False
    mock_current_user = mocker.patch("invenio_sipstore.api.current_user")
    type(mock_current_user).is_anonymous = mocker.PropertyMock(return_value=True)
    sip = SIP.create(True, files=files, metadata=metadata)
    assert sip.model.user_id is None
    assert sip.user is None
    assert sip.agent == {}
    # finalization
    rmtree(tmppath)


def test_RecordSIP(db, locations, minimal_record):
    """Test RecordSIP API class."""
    user = create_test_user("test@example.org")
    agent = {"email": "user@invenio.org", "ip_address": "1.1.1.1"}
    # we create a record
    metadata = {**minimal_record, "files": {"enabled": False}}
    draft = records_service.create(system_identity, metadata)
    record = records_service.publish(system_identity, draft.id)._record

    # we create the models
    sip = SIP.create(True, user_id=user.id, agent=agent)
    recordsip = RecordSIP_(sip_id=sip.id, pid_id=record.pid.pid_value)
    db.session.commit()
    # We create an API SIP on top of it
    api_recordsip = RecordSIP(recordsip, sip)
    assert api_recordsip.model is recordsip
    assert api_recordsip.sip.id == sip.id


def test_RecordSIP_create(app, db, mocker, minimal_record):
    """Test create method from the API class RecordSIP."""
    # we setup a file storage
    tmppath = tempfile.mkdtemp()
    db.session.add(Location(name="default", uri=tmppath, default=True))
    # setup metadata
    mtype = SIPMetadataType(
        title="JSON Test",
        name="json-test",
        format="json",
        schema=records_service.record_cls.schema.value,
    )
    db.session.add(mtype)
    db.session.commit()

    # first we create a record
    draft = records_service.create(system_identity, minimal_record)
    draft._obj.bucket.default_storage_class = "L"
    records_service.draft_files.init_files(
        system_identity, draft.id, [{"key": "test.txt"}]
    )
    records_service.draft_files.set_file_content(
        system_identity, draft.id, "test.txt", BytesIO(b"test file")
    )
    records_service.draft_files.commit_file(system_identity, draft.id, "test.txt")
    record = records_service.publish(system_identity, draft.id)._record
    db.session.commit()

    # Let's create a SIP
    user = create_test_user("test@example.org")
    agent = {"email": "user@invenio.org", "ip_address": "1.1.1.1"}
    rsip = RecordSIP.create(record, True, user_id=user.id, agent=agent)
    db.session.commit()

    # test!
    assert RecordSIP_.query.count() == 1
    assert SIP_.query.count() == 1
    assert SIPFile.query.count() == 1
    assert SIPMetadata.query.count() == 1
    assert len(rsip.sip.files) == 1
    assert len(rsip.sip.metadata) == 1
    metadata = rsip.sip.metadata[0]
    assert metadata.type.format == "json"
    assert metadata.content == json.dumps(record.dumps())
    assert rsip.sip.archivable is True

    # we try with no files
    rsip = RecordSIP.create(
        record, True, create_sip_files=False, user_id=user.id, agent=agent
    )
    assert SIPFile.query.count() == 1
    assert SIPMetadata.query.count() == 2
    assert len(rsip.sip.files) == 0
    assert len(rsip.sip.metadata) == 1

    # try with specific SIP metadata type
    mtype = SIPMetadataType(
        title="JSON Test 2", name="json-test-2", format="json", schema=None
    )  # no schema
    db.session.add(mtype)
    db.session.commit()

    rsip = RecordSIP.create(
        record,
        True,
        create_sip_files=False,
        user_id=user.id,
        agent=agent,
        sip_metadata_type="json-test-2",
    )
    assert SIPMetadata.query.count() == 3
    assert len(rsip.sip.metadata) == 1
    assert rsip.sip.metadata[0].type.id == mtype.id

    # finalization
    rmtree(tmppath)
