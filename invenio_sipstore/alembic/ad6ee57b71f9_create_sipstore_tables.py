# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2017-2019 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Create sipstore tables."""

import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op
from sqlalchemy.dialects import mysql, postgresql

# revision identifiers, used by Alembic.
revision = 'ad6ee57b71f9'
down_revision = 'ac2d9845d16f'
branch_labels = ()
depends_on = (
    '9848d0149abd',  # invenio-accounts
    '2e97565eba72',  # invenio-files-rest
    '999c62899c20',  # invenio-pidstore
)


def upgrade():
    """Upgrade database."""
    op.create_table(
        'sipstore_sip',
        sa.Column('created', sa.DateTime(), nullable=False),
        sa.Column('updated', sa.DateTime(), nullable=False),
        sa.Column(
            'id', sqlalchemy_utils.types.uuid.UUIDType(),
            nullable=False),
        sa.Column('sip_format', sa.String(length=7), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column(
            'agent',
            sqlalchemy_utils.JSONType().with_variant(
                postgresql.JSON(none_as_null=True), 'postgresql'),
            nullable=False),
        sa.ForeignKeyConstraint(
            ['user_id'], [u'accounts_user.id'],
            name='fk_sipstore_sip_user_id'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'sipstore_recordsip',
        sa.Column('created', sa.DateTime(), nullable=False),
        sa.Column('updated', sa.DateTime(), nullable=False),
        sa.Column(
            'sip_id', sqlalchemy_utils.types.uuid.UUIDType(),
            nullable=False),
        sa.Column('pid_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['pid_id'], [u'pidstore_pid.id'],
            name='fk_sipstore_recordsip_pid_id'),
        sa.ForeignKeyConstraint(
            ['sip_id'], [u'sipstore_sip.id'],
            name='fk_sipstore_recordsip_sip_id'),
        sa.PrimaryKeyConstraint('sip_id', 'pid_id')
    )
    op.create_table(
        'sipstore_sipfile',
        sa.Column('created', sa.DateTime(), nullable=False),
        sa.Column('updated', sa.DateTime(), nullable=False),
        sa.Column(
            'sip_id', sqlalchemy_utils.types.uuid.UUIDType(),
            nullable=False),
        sa.Column(
            'filepath',
            sa.Text().with_variant(mysql.VARCHAR(255), 'mysql'),
            nullable=True
        ),
        sa.Column(
            'file_id', sqlalchemy_utils.types.uuid.UUIDType(),
            nullable=False),
        sa.ForeignKeyConstraint(
            ['file_id'], [u'files_files.id'],
            name='fk_sipstore_sipfile_file_id',
            ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(
            ['sip_id'], [u'sipstore_sip.id'],
            name='fk_sipstore_sipfile_sip_id'),
        sa.PrimaryKeyConstraint('sip_id', 'filepath')
    )


def downgrade():
    """Downgrade database."""
    op.drop_table('sipstore_sipfile')
    op.drop_table('sipstore_recordsip')
    op.drop_table('sipstore_sip')
