# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016-2019 CERN.
# Copyright (C) 2024 TU Wien.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""API for Invenio-SIPStore."""

import json

from flask import current_app, has_request_context, request
from flask_login import current_user
from invenio_db import db
from werkzeug.utils import import_string

from invenio_sipstore.models import SIP as SIP_
from invenio_sipstore.models import RecordSIP as RecordSIP_
from invenio_sipstore.models import SIPFile, SIPMetadata, SIPMetadataType
from invenio_sipstore.signals import sipstore_created


class SIP:
    """API for managing SIPs."""

    def __init__(self, sip):
        """Constructor.

        :param sip: the SIP model associated
        :type sip: :py:class:`invenio_sipstore.models.SIP`
        """
        self.model = sip

    @property
    def id(self):
        """Return the ID of the associated model."""
        return self.model.id

    # read only as it shouldn't change
    @property
    def user(self):
        """Return the user of the associated model."""
        return self.model.user

    # read only as it shouldn't change
    @property
    def agent(self):
        """Return the agent of the associated model."""
        return self.model.agent

    # read only as it shouldn't change
    @property
    def archivable(self):
        """Tell if the SIP should be archived."""
        return self.model.archivable

    # read only as it shouldn't change
    @property
    def archived(self):
        """Tell if the SIP has been archived."""
        return self.model.archived

    @archived.setter
    def archived(self, is_archived):
        """Change the archived status of the SIP.

        :param bool is_archived: True if the SIP has been archived
        """
        self.model.archived = is_archived

    @property
    def files(self):
        """Return the list of files associated with the SIP.

        :rtype: list(:py:class:`invenio_sipstore.models.SIPFile`)
        """
        return self.model.sip_files

    @property
    def metadata(self):
        """Return the list of metadata associated with the SIP.

        :rtype: list(:py:class:`invenio_sipstore.models.SIPMetadata`)
        """
        return self.model.sip_metadata

    def attach_file(self, file):
        """Add a file to the SIP.

        :param file: the file to attach. It must at least implement a `key`
            and a valid `file_id`. See
            :py:class:`invenio_files_rest.models.ObjectVersion`.
        :returns: the created SIPFile
        :rtype: :py:class:`invenio_sipstore.models.SIPFile`
        """
        sf = SIPFile(sip_id=self.id, filepath=file.key, file_id=file.file_id)
        db.session.add(sf)
        return sf

    def attach_metadata(self, type, metadata):
        """Add metadata to the SIP.

        :param str type: the type of metadata (a valid
            :py:class:`invenio_sipstore.models.SIPMetadataType` name)
        :param str metadata: the metadata to attach.
        :returns: the created SIPMetadata
        :rtype: :py:class:`invenio_sipstore.models.SIPMetadata`
        """
        mtype = SIPMetadataType.get_from_name(type)
        sm = SIPMetadata(sip_id=self.id, type=mtype, content=metadata)
        db.session.add(sm)
        return sm

    @classmethod
    def create(cls, archivable, files=None, metadata=None, user_id=None, agent=None):
        """Create a SIP, from the PID and the Record.

        Apart from the SIP itself, it also creates ``SIPFile`` objects for
        each of the files in the record, along with ``SIPMetadata`` for the
        metadata.
        Those objects are not returned by this function but can be fetched by
        the corresponding SIP attributes 'files' and 'metadata'.
        The created model is stored in the attribute 'model'.

        :param bool archivable: tells if the SIP should be archived or not.
            Usefull if ``Invenio-Archivematica`` is installed.
        :param files: The list of files to associate with the SIP. See
            :py:func:`invenio_sipstore.api.SIP.attach_file`
        :param dict metadata: A dictionary of metadata. The keys are the
            type (valid :py:class:`invenio_sipstore.models.SIPMetadataType`
            name) and the values are the content (string)
        :param user_id: the ID of the user. If not given, automatically
            computed
        :param agent: If not given, automatically computed
        :returns: API SIP object.
        :rtype: :py:class:`invenio_sipstore.api.SIP`
        """
        if not user_id:
            user_id = (
                None
                if not current_user or current_user.is_anonymous
                else current_user.get_id()
            )
        if not agent:
            agent_factory = import_string(current_app.config["SIPSTORE_AGENT_FACTORY"])
            agent = agent_factory()
        files = [] if not files else files
        metadata = {} if not metadata else metadata

        with db.session.begin_nested():
            sip = cls(SIP_.create(user_id=user_id, agent=agent, archivable=archivable))
            for f in files:
                sip.attach_file(f)
            for type, content in metadata.items():
                sip.attach_metadata(type, content)
        sipstore_created.send(sip)
        return sip

    @classmethod
    def get_sip(cls, uuid):
        """Get a SIP API object from the UUID if a model object."""
        return cls(db.session.query(SIP_).get(uuid))


class RecordSIP:
    """API for managing SIPRecords."""

    def __init__(self, recordsip, sip):
        """Constructor.

        :param recordsip: the RecordSIP model to manage
        :type recordsip: :py:class:`invenio_sipstore.models.RecordSIP`
        :param sip: the SIP associated
        :type sip: :py:class:`invenio_sipstore.api.SIP`
        """
        self.model = recordsip
        self._sip = sip

    # we make it unwritable
    @property
    def sip(self):
        """Return the SIP corresponding to this record.

        :rtype: :py:class:`invenio_sipstore.api.SIP`
        """
        return self._sip

    @classmethod
    def create(
        cls,
        record,
        archivable,
        create_sip_files=True,
        user_id=None,
        agent=None,
        sip_metadata_type=None,
    ):
        """Create a SIP from the Record.

        Apart from the SIP itself, it also creates ``RecordSIP`` for the
        SIP-PID-Record relationship, as well as ``SIPFile`` objects for each
        of the files in the record, along with ``SIPMetadata`` for the
        metadata.
        Those objects are not returned by this function but can be fetched by
        the corresponding RecordSIP attributes ``sip``, ``sip.files`` and
        ``sip.metadata``.

        :param record: Record for which the SIP should be created.
        :type record: :py:class:`invenio_records.api.Record`
        :param bool archivable: tells if the record should be archived.
            Usefull when ``Invenio-Archivematica`` is installed.
        :param bool create_sip_files: If True the SIPFiles will be created.
        :param str sip_metadata_type: Used to fetch the
            :py:class:`invenio_sipstore.models.SIPMetadataType` by ``name``.
            If not provided, the ``$schema`` attribute of ``record`` will be
            used to determine the
            :py:class:`invenio_sipstore.models.SIPMetadataType`.
            (default: ``None``)
        :returns: RecordSIP object.
        :rtype: :py:class:`invenio_sipstore.api.RecordSIP`
        """
        if create_sip_files and record.files.enabled:
            files = [rf.file for rf in record.files.values()]
        else:
            files = []

        if sip_metadata_type:
            mtype = SIPMetadataType.get_from_name(sip_metadata_type)
        else:
            mtype = SIPMetadataType.get_from_schema(record["$schema"])

        metadata = {mtype.name: json.dumps(record.dumps())}

        with db.session.begin_nested():
            sip = SIP.create(
                archivable, files=files, metadata=metadata, user_id=user_id, agent=agent
            )
            model = RecordSIP_(sip_id=sip.id, pid_id=record.pid.id)
            db.session.add(model)
            recsip = cls(model, sip)

        return recsip


def default_agent_info_builder():
    """Default builder for the SIP agent info, with IP and email address.

    This method can be changed in the config to suit your needs, see
    :py:data:`invenio_sipstore.config.SIPSTORE_AGENT_FACTORY`

    :returns: Agent information regarding the SIP.
    :rtype: dict
    """
    agent = {}
    if has_request_context() and request.remote_addr:
        agent["ip_address"] = request.remote_addr
        if current_user and current_user.is_authenticated and current_user.email:
            agent["email"] = current_user.email

    return agent
