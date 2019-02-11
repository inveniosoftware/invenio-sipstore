# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016-2019 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.


"""Module tests."""

from __future__ import absolute_import, print_function

import pytest
from flask import Flask

from invenio_sipstore import InvenioSIPStore


def test_version():
    """Test version import."""
    from invenio_sipstore import __version__
    assert __version__


def test_init():
    """Test extension initialization."""
    app = Flask('testapp')
    ext = InvenioSIPStore(app)
    assert 'invenio-sipstore' in app.extensions

    app = Flask('testapp')
    ext = InvenioSIPStore()
    assert 'invenio-sipstore' not in app.extensions
    ext.init_app(app)
    assert 'invenio-sipstore' in app.extensions


def test_alembic(app, db):
    """Test alembic recipes."""
    ext = app.extensions['invenio-db']

    if db.engine.name == 'sqlite':
        raise pytest.skip('Upgrades are not supported on SQLite.')

    assert not ext.alembic.compare_metadata()
    db.drop_all()
    ext.alembic.upgrade()

    assert not ext.alembic.compare_metadata()
    ext.alembic.stamp()
    ext.alembic.downgrade(target='96e796392533')
    ext.alembic.upgrade()

    assert not ext.alembic.compare_metadata()
