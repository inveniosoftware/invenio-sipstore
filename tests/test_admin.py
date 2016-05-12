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
"""Admin interface tests."""

from __future__ import absolute_import, print_function

from flask_admin import Admin, menu

from invenio_sipstore.admin import recordsip_adminview, sip_adminview, \
    sipfile_adminview


def test_admin(db, app):
    """Test flask-admin interace."""
    admin = Admin(app, name="AdminExt")

    # Register models in admin
    for adminview in (sip_adminview, sipfile_adminview, recordsip_adminview):
        assert 'model' in adminview
        assert 'modelview' in adminview
        admin_kwargs = dict(adminview)
        model = admin_kwargs.pop('model')
        modelview = admin_kwargs.pop('modelview')
        admin.add_view(modelview(model, db.session, **admin_kwargs))

    # Check if generated admin menu contains the correct items
    menu_items = {str(item.name): item for item in admin.menu()}

    # PIDStore should be a category
    assert 'Records' in menu_items
    assert menu_items['Records'].is_category()
    assert isinstance(menu_items['Records'], menu.MenuCategory)

    # Items in PIDStore menu should be the modelviews
    submenu_items = {str(item.name): item for item in
                     menu_items['Records'].get_children()}
    assert 'SIP' in submenu_items
    assert 'RecordSIP' in submenu_items
    assert 'SIPFile' in submenu_items
    assert isinstance(submenu_items['SIP'], menu.MenuView)
    assert isinstance(submenu_items['RecordSIP'], menu.MenuView)
    assert isinstance(submenu_items['SIPFile'], menu.MenuView)
