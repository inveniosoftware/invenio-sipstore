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

"""Invenio-SIPStore database models."""

from __future__ import absolute_import, print_function

import uuid

from flask import current_app
from invenio_accounts.models import User
from invenio_db import db
from invenio_files_rest.models import FileInstance
from invenio_jsonschemas.errors import JSONSchemaNotFound
from invenio_pidstore.models import PersistentIdentifier
from jsonschema import validate
from sqlalchemy_utils.models import Timestamp
from sqlalchemy_utils.types import JSONType, UUIDType
from werkzeug.local import LocalProxy

from .errors import SIPUserDoesNotExist

current_jsonschemas = LocalProxy(
    lambda: current_app.extensions['invenio-jsonschemas']
)


class SIP(db.Model, Timestamp):
    """Submission Information Package model."""

    __tablename__ = 'sipstore_sip'

    id = db.Column(UUIDType, primary_key=True, default=uuid.uuid4)
    """Id of SIP."""

    sip_format = db.Column(db.String(7), nullable=False)
    """Format of the SIP content ('json', 'marcxml' etc.)"""

    content = db.Column(db.Text, nullable=False)
    """Text blob of the SIP content."""

    user_id = db.Column(db.Integer,
                        db.ForeignKey(User.id),
                        nullable=True,
                        default=None)
    """User responsible for the SIP."""

    agent = db.Column(JSONType, default=lambda: dict(), nullable=False)
    """Agent information regarding given SIP."""

    #
    # Relationships
    #
    user = db.relationship(User, backref='sips', foreign_keys=[user_id])
    """Relation to the User responsible for the SIP."""

    @classmethod
    def create(cls, sip_format, content, user_id=None, agent=None):
        """Create a Submission Information Package object.

        :param sip_format: Format of the SIP content (e.g. 'json', 'marcxml').
        :type sip_format: str
        :param content: Text blob of the SIP content.
        :type content: str
        :param user_id: Id of the user responsible for the SIP.
        :type user_id: int
        :param agent: Extra information on submitting agent in JSON format.
        :type agent: dict
        """
        if user_id and (User.query.get(user_id) is None):
            raise SIPUserDoesNotExist(user_id)

        agent = agent or dict()

        if current_app.config['SIPSTORE_AGENT_JSONSCHEMA_ENABLED']:
            agent.setdefault('$schema', current_jsonschemas.path_to_url(
                current_app.config['SIPSTORE_DEFAULT_AGENT_JSONSCHEMA']))
            schema_path = current_jsonschemas.url_to_path(agent['$schema'])
            if not schema_path:
                raise JSONSchemaNotFound(agent['$schema'])

            schema = current_jsonschemas.get_schema(schema_path)
            validate(agent, schema)

        with db.session.begin_nested():
            obj = cls(sip_format=sip_format, content=content, user_id=user_id,
                      agent=agent)
            db.session.add(obj)
        return obj


class SIPFile(db.Model, Timestamp):
    """Extra SIP info regarding files."""

    __tablename__ = 'sipstore_sipfile'

    sip_id = db.Column(UUIDType, db.ForeignKey(SIP.id))
    """Id of SIP."""

    filepath = db.Column(db.String(255), nullable=False)
    """Filepath of submitted file within the SIP record."""

    file_id = db.Column(
        UUIDType,
        db.ForeignKey(FileInstance.id, ondelete='RESTRICT'),
        primary_key=True,
        nullable=False)
    """Id of the FileInstance."""

    #
    # Relations
    #
    sip = db.relationship(SIP, backref='sip_files', foreign_keys=[sip_id])
    """Relation to the SIP along which given file was submitted."""

    file = db.relationship(FileInstance, backref='sip_files',
                           foreign_keys=[file_id])
    """Relation to the SIP along which given file was submitted."""


class RecordSIP(db.Model, Timestamp):
    """An association table for Records and SIPs."""

    __tablename__ = 'sipstore_recordsip'

    sip_id = db.Column(UUIDType, db.ForeignKey(SIP.id),
                       primary_key=True)
    """Id of SIP."""

    pid_id = db.Column(db.Integer, db.ForeignKey(PersistentIdentifier.id),
                       primary_key=True)
    """Id of the PID pointing to the record."""

    #
    # Relations
    #
    sip = db.relationship(SIP, backref='record_sips', foreign_keys=[sip_id])
    """Relation to the SIP associated with the record."""
