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
from invenio_files_rest.models import FileInstance
from invenio_jsonschemas.errors import JSONSchemaNotFound
from invenio_pidstore.models import PersistentIdentifier
from jsonschema.exceptions import ValidationError

from invenio_sipstore.errors import SIPUserDoesNotExist
from invenio_sipstore.models import SIP, RecordSIP, SIPFile


def test_sip_model(db):
    """Test the SIP model."""
    user1 = create_test_user()

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
    sip1 = SIP.create('json', '{"foo": "bar"}', user_id=user1.id,
                      agent=agent1)
    assert sip1.user == user1

    SIP.create('marcxml', '<foo>bar</foo>')
    SIP.create('json', '{}', user_id=user1.id, agent=agent1)
    assert SIP.query.count() == 3

    pytest.raises(ValidationError, SIP.create, 'json', '{}', agent=agent2)
    pytest.raises(SIPUserDoesNotExist, SIP.create, 'json', '{}', user_id=5)
    pytest.raises(JSONSchemaNotFound, SIP.create, 'json', '', agent=agent3)
    db.session.commit()


def test_sip_file_model(db):
    """Test the SIPFile model."""
    sip1 = SIP.create('json', '{}')
    file1 = FileInstance.create()
    sipfile1 = SIPFile(sip_id=sip1.id, filepath="foobar.zip",
                       file_id=file1.id)

    db.session.add(sipfile1)
    db.session.commit()
    assert SIP.query.count() == 1
    assert SIPFile.query.count() == 1


def test_record_sip_model(db):
    """Test the RecordSIP model."""
    sip1 = SIP.create('json', '{}')
    db.session.commit()
    pid1 = PersistentIdentifier.create('recid', '12345')

    rsip1 = RecordSIP(sip_id=sip1.id, pid_id=pid1.id)
    db.session.add(rsip1)
    db.session.commit()
    assert RecordSIP.query.count() == 1
