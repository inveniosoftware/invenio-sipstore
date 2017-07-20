#
# This file is part of Invenio.
# Copyright (C) 2017 CERN.
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

"""Extend SIP metadata model."""

import sqlalchemy_utils
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'b31cad2f14c7'
down_revision = 'ad6ee57b71f9'
branch_labels = ()
depends_on = None


def upgrade():
    """Upgrade database.

    This migration brings the database to a state that has all the tables which
    allow the application code to run, without migrating though any of the
    actual data. This allows for a later separate migration step for the data
    while the system is still operational.

    The main reason this is possible, is because of the fact that the tables
    used are "write-only" (archiving of the SIP entries can be manually enabled
    and executed in the future by an administrator), which is a pretty rare
    case.

    Example upgrade plan (assumes old application code is deployed/running):

    1. `inveniomanage alembic upgrade b31cad2f14c7`
    2. Upgrade application code
    3. If neccessary, run any required fixtures
       (eg. `inveniomanage fixtures load-sip-metadata-types`)
    4. Restart running applications (WSGI apps and/or Celery workers)
    5. `inveniomanage alembic upgrade 1c4e509ccacc`
    """
    op.create_table(
        'sipstore_sipmetadatatype',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('format', sa.String(255), nullable=False),
        sa.Column('schema', sa.String(1024), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_sipstore_sipmetadatatype_name'),
        sa.UniqueConstraint(
            'schema', name='uq_sipstore_sipmetadatatype_schema')
    )
    op.create_table(
        'sipstore_sipmetadata',
        sa.Column('created', sa.DateTime(), nullable=False),
        sa.Column('updated', sa.DateTime(), nullable=False),
        sa.Column('sip_id', sqlalchemy_utils.types.uuid.UUIDType(),
                  nullable=False),
        sa.Column('type_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ['sip_id'], [u'sipstore_sip.id'], name='fk_sipmetadata_sip_id'),
        sa.ForeignKeyConstraint(
            ['type_id'], [u'sipstore_sipmetadatatype.id'],
            name='fk_sipmetadatatype_type'),
        sa.PrimaryKeyConstraint('sip_id', 'type_id')
    )

    # Add SIP 'archivable' and 'archived' columns without the NULL constraint
    op.add_column(
        'sipstore_sip', sa.Column('archivable', sa.Boolean(name='archivable')))
    op.add_column(
        'sipstore_sip', sa.Column('archived', sa.Boolean(name='archived')))

    # Update the columns with default values
    SIP = sa.sql.table(
        'sipstore_sip', sa.sql.column('archivable'), sa.sql.column('archived'))
    op.execute(SIP.update().values(**{'archivable': True, 'archived': False}))

    # Set the old SIP metadata columns to be nullable, so that new records
    op.alter_column('sipstore_sip', 'sip_format', nullable=True)
    op.alter_column('sipstore_sip', 'content', nullable=True)


def downgrade():
    """Downgrade database.

    This downgrade recipe migrates data that were created with the future
    model, to the old model that might be running on the application server.

    Because of the difference in the relationship cradinality between a SIP and
    its Metadata between the old and new model, it is only possible to perform
    this downgrade in case that SIP metadata of only one type exist per SIP
    (eg. only 'json').
    """
    metadata = sa.MetaData()

    # Helper tables from old model
    SIPMetadata = sa.Table(
        'sipstore_sipmetadata',
        metadata,
        sa.Column('sip_id', sqlalchemy_utils.types.uuid.UUIDType()),
        sa.Column('type_id', sa.Integer()),
        sa.Column('content', sa.Text())
    )
    SIPMetadataType = sa.Table(
        'sipstore_sipmetadatatype',
        metadata,
        sa.Column('id', sa.Integer()),
        sa.Column('name', sa.String(255)),
    )
    SIP = sa.Table(
        'sipstore_sip',
        metadata,
        sa.Column('id', sqlalchemy_utils.types.uuid.UUIDType()),
        sa.Column('sip_format', sa.String(7)),
        sa.Column('content', sa.Text()),
    )

    conn = op.get_bind()

    # Check if downgrade is possible.
    multi_typed_metadata_sips = sa.exists(
        sa.select([SIPMetadata.c.sip_id])
        .group_by(SIPMetadata.c.sip_id)
        .having(sa.func.count() > 1))
    if conn.execute(sa.select([multi_typed_metadata_sips])).scalar():
        raise Exception('You have multiple types of SIP metadata for some '
                        'SIPs. Automatic downgrade not possible...')

    # Create SIP metadata type id-to-name mapping
    sip_mtypes = dict(iter(conn.execute(
        sa.select([SIPMetadataType.c.id, SIPMetadataType.c.name]))))
    if any(v for v in sip_mtypes.values() if len(v) > 7):
        raise Exception(
            'You have SIP metadata type names longer than 7 characters. '
            'Shorten the names to perform the downgrade...')
    sip_metadata_type_mapping = sa.case(
        sip_mtypes, value=SIPMetadata.c.type_id)

    # Migrate SIP metadata back to SIP table
    op.execute(SIP.update().values(
        content=SIPMetadata.c.content, sip_format=sip_metadata_type_mapping)
        .where(SIP.c.id == SIPMetadata.c.sip_id))

    # Remove 'archived' and 'archivable' columns
    op.drop_column('sipstore_sip', 'archived')
    op.drop_column('sipstore_sip', 'archivable')

    # Remove the new tables
    op.drop_table('sipstore_sipmetadata')
    op.drop_table('sipstore_sipmetadatatype')

    # Add the NOT NULL constraint to 'sip_format' and 'content'
    op.alter_column('sipstore_sip', 'sip_format', nullable=False)
    op.alter_column('sipstore_sip', 'content', nullable=False)
