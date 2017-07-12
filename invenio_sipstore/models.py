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
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import validates
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

    user_id = db.Column(
        db.Integer,
        db.ForeignKey(User.id, name='fk_sipstore_sip_user_id'),
        nullable=True,
        default=None)
    """User responsible for the SIP."""

    agent = db.Column(JSONType, default=lambda: dict(), nullable=False)
    """Agent information regarding given SIP."""

    archivable = db.Column(
        db.Boolean(name='archivable'),
        nullable=False,
        default=True)
    """Boolean stating if the SIP should be archived or not."""

    archived = db.Column(
        db.Boolean(name='archived'),
        nullable=False,
        default=False)
    """Boolean stating if the SIP has been archived or not."""

    #
    # Relationships
    #
    user = db.relationship(User, backref='sips', foreign_keys=[user_id])
    """Relation to the User responsible for the SIP."""

    @classmethod
    def create(cls, user_id=None, agent=None, id_=None, archivable=True,
               archived=False):
        """Create a Submission Information Package object.

        :param user_id: Id of the user responsible for the SIP.
        :type user_id: int
        :param agent: Extra information on submitting agent in JSON format.
        :type agent: dict
        :param bool archivable: Tells if the SIP should be archived or not.
        :param bool archived: Tells if the SIP has been archived.
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
            obj = cls(
                id=id_ or uuid.uuid4(),
                user_id=user_id,
                agent=agent,
                archivable=archivable,
                archived=archived
            )
            db.session.add(obj)
        return obj


class SIPFile(db.Model, Timestamp):
    """Extra SIP info regarding files."""

    __tablename__ = 'sipstore_sipfile'

    sip_id = db.Column(
        UUIDType,
        db.ForeignKey(SIP.id, name='fk_sipstore_sipfile_sip_id'),
        primary_key=True)
    """Id of SIP."""

    filepath = db.Column(
        db.Text().with_variant(mysql.VARCHAR(255), 'mysql'), nullable=False,
        primary_key=True)
    """Filepath of submitted file within the SIP record."""

    file_id = db.Column(
        UUIDType,
        db.ForeignKey(FileInstance.id, name='fk_sipstore_sipfile_file_id',
                      ondelete='RESTRICT'),
        nullable=False)
    """Id of the FileInstance."""

    @property
    def checksum(self):
        """Return the checksum of the file."""
        return self.file.checksum

    @property
    def size(self):
        """Return the size of the file."""
        return self.file.size

    @property
    def storage_location(self):
        """Return the location of the file in the current storage."""
        return self.file.uri

    @validates('filepath')
    def validate_key(self, filepath, filepath_):
        """Validate key."""
        if len(filepath_) > current_app.config['SIPSTORE_FILEPATH_MAX_LEN']:
            raise ValueError(
                'Filepath too long ({0}).'.format(len(filepath_)))
        return filepath_

    #
    # Relations
    #
    sip = db.relationship(SIP, backref='sip_files', foreign_keys=[sip_id])
    """Relation to the SIP along which given file was submitted."""

    file = db.relationship(FileInstance, backref='sip_files',
                           foreign_keys=[file_id])
    """Relation to the SIP along which given file was submitted."""


class SIPMetadataType(db.Model):
    """Type of the metadata added to an SIP.

    The type describes the type of file along with an eventual schema used to
    validate the structure of the content.
    """

    __tablename__ = 'sipstore_sipmetadatatype'

    id = db.Column(db.Integer(), primary_key=True)
    """ID of the SIPMetadataType object."""

    title = db.Column(db.String(255), nullable=False)
    """The title of type of metadata (i.e. 'Invenio JSON Record v1.0.0')."""

    name = db.Column(db.String(255), nullable=False, unique=True)
    """The unique name tag of the metadata type."""

    format = db.Column(db.String(255), nullable=False)
    """The format of the metadata (xml, json, txt...).

    This is used as the extension of the created file during an export.
    """

    schema = db.Column(db.String(1024), nullable=True, unique=True)
    """URI to a schema that describes the metadata (json or xml schema)."""

    @classmethod
    def get(cls, id):
        """Return the corresponding SIPMetadataType."""
        return cls.query.filter_by(id=id).one()

    @classmethod
    def get_from_name(cls, name):
        """Return the corresponding SIPMetadataType."""
        return cls.query.filter_by(name=name).one()

    @classmethod
    def get_from_schema(cls, schema):
        """Return the corresponding SIPMetadataType."""
        return cls.query.filter_by(schema=schema).one()


class SIPMetadata(db.Model, Timestamp):
    """Extra SIP info regarding metadata."""

    __tablename__ = 'sipstore_sipmetadata'

    sip_id = db.Column(UUIDType,
                       db.ForeignKey(SIP.id, name='fk_sipmetadata_sip_id'),
                       primary_key=True)
    """Id of SIP."""

    type_id = db.Column(db.Integer(),
                        db.ForeignKey(SIPMetadataType.id,
                                      name='fk_sipmetadatatype_type'),
                        primary_key=True)
    """ID of the metadata type."""

    content = db.Column(db.Text, nullable=False)
    """Text blob of the metadata content."""

    #
    # Relations
    #
    sip = db.relationship(SIP, backref='sip_metadata', foreign_keys=[sip_id])
    """Relation to the SIP along which given metadata was submitted."""

    type = db.relationship(SIPMetadataType)
    """Relation to the SIPMetadataType."""


class RecordSIP(db.Model, Timestamp):
    """An association table for Records and SIPs."""

    __tablename__ = 'sipstore_recordsip'

    sip_id = db.Column(
        UUIDType,
        db.ForeignKey(SIP.id, name='fk_sipstore_recordsip_sip_id'),
        primary_key=True)
    """Id of SIP."""

    pid_id = db.Column(
        db.Integer,
        db.ForeignKey(PersistentIdentifier.id,
                      name='fk_sipstore_recordsip_pid_id'),
        primary_key=True)
    """Id of the PID pointing to the record."""

    #
    # Relations
    #
    sip = db.relationship(SIP, backref='record_sips', foreign_keys=[sip_id])
    """Relation to the SIP associated with the record."""
