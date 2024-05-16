# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016-2019 CERN.
# Copyright (C) 2024 TU Wien.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.


"""Module tests."""

import pytest
from flask import Flask
from invenio_db.utils import alembic_test_context, drop_alembic_version_table

from invenio_sipstore import InvenioSIPStore


def test_version():
    """Test version import."""
    from invenio_sipstore import __version__

    assert __version__


def test_init():
    """Test extension initialization."""
    app = Flask("testapp")
    ext = InvenioSIPStore(app)
    assert "invenio-sipstore" in app.extensions

    app = Flask("testapp")
    ext = InvenioSIPStore()
    assert "invenio-sipstore" not in app.extensions
    ext.init_app(app)
    assert "invenio-sipstore" in app.extensions


@pytest.mark.skip("Skipped for now, due to a mess after changes in Invenio-Accounts")
def test_alembic(base_app, database):
    """Test alembic recipes."""
    ext = base_app.extensions["invenio-db"]

    if database.engine.name == "sqlite":
        raise pytest.skip("Upgrades are not supported on SQLite.")

    base_app.config["ALEMBIC_CONTEXT"] = alembic_test_context()

    assert not ext.alembic.compare_metadata()
    database.drop_all()
    drop_alembic_version_table()
    ext.alembic.upgrade()

    assert not ext.alembic.compare_metadata()
    ext.alembic.stamp()
    ext.alembic.downgrade(target="96e796392533")
    ext.alembic.upgrade()

    assert not ext.alembic.compare_metadata()
    drop_alembic_version_table()
