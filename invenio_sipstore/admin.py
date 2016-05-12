# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016 CERN.
#
# Invenio is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""Admin model views for SIPStore."""

from flask_admin.contrib.sqla import ModelView

from .models import SIP, RecordSIP, SIPFile


class SIPModelView(ModelView):
    """ModelView for the SIP."""

    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    column_display_all_relations = True
    column_list = (
        'sip_format', 'content', 'user_id', 'agent'
    )
    column_labels = dict(
        sip_format='SIP Format',
        content='Content',
        user_id='User ID',
        agent='Agent'
    )
    column_filters = (
        'sip_format', 'content', 'user_id',
    )
    column_searchable_list = ('sip_format', 'content')
    page_size = 25


class SIPFileModelView(ModelView):
    """ModelView for the SIPFile."""

    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
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
recordsip_adminview = dict(
    modelview=RecordSIPModelView,
    model=RecordSIP,
    name='RecordSIP',
    category='Records')
