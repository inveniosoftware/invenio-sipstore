# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016-2019 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Admin model views for SIPStore."""

from flask_admin.contrib.sqla import ModelView

from .models import SIP, RecordSIP, SIPFile, SIPMetadata, SIPMetadataType


class SIPModelView(ModelView):
    """ModelView for the SIP."""

    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    column_display_all_relations = True
    column_list = (
        'id', 'user_id', 'agent', 'archivable', 'archived'
    )
    column_labels = {
        'id': 'UUID',
        'user_id': 'User ID',
        'agent': 'Agent',
        'archivable': 'Archivable',
        'archived': 'Archived'
    }
    column_filters = (
        'user_id', 'archivable', 'archived'
    )
    column_searchable_list = ('id', 'user_id', 'agent', )
    page_size = 25


class SIPFileModelView(ModelView):
    """ModelView for the SIPFile."""

    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    page_size = 25


class SIPMetadataModelView(ModelView):
    """ModelView for the SIPMetadata."""

    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    column_display_all_relations = True
    column_list = (
        'type.name',
        'content',
        'sip.id',
        'sip.agent',
        'sip.archivable',
        'sip.archived'
    )
    column_labels = {
        'type.name': 'Type',
        'content': 'Content',
        'sip.id': 'SIP',
        'sip.agent': 'Agent',
        'sip.archivable': 'Archivable',
        'sip.archived': 'Archived'
    }
    page_size = 25


class SIPMetadataTypeModelView(ModelView):
    """ModelView for the SIPMetadataType."""

    can_create = True
    can_edit = True
    can_delete = False
    can_view_details = True
    column_display_all_relations = True
    page_size = 25


class RecordSIPModelView(ModelView):
    """ModelView for the RecordSIP."""

    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    page_size = 25


sip_adminview = dict(
    modelview=SIPModelView,
    model=SIP,
    name='SIP',
    category='Records')
sipfile_adminview = dict(
    modelview=SIPFileModelView,
    model=SIPFile,
    name='SIPFile',
    category='Records')
sipmetadata_adminview = dict(
    modelview=SIPMetadataModelView,
    model=SIPMetadata,
    name='SIPMetadata',
    category='Records')
sipmetadatatype_adminview = dict(
    modelview=SIPMetadataTypeModelView,
    model=SIPMetadataType,
    name='SIPMetadataType',
    category='Records')
recordsip_adminview = dict(
    modelview=RecordSIPModelView,
    model=RecordSIP,
    name='RecordSIP',
    category='Records')
