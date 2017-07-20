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

"""Migrate SIP metadata."""

from __future__ import print_function

import os
import sqlalchemy_utils
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '1c4e509ccacc'
down_revision = 'b31cad2f14c7'
branch_labels = ()
depends_on = None


def upgrade():
    """Upgrade database.

    This upgrade aims at migrating the SIP metadata available in "SIP.content".
    It can be executed while the application instance is still running.
    """
    metadata = sa.MetaData()

    # Field-only definition of old SIP table to help with data migration
    OldSIP = sa.Table(
        'sipstore_sip',
        metadata,
        sa.Column('id', sqlalchemy_utils.types.uuid.UUIDType()),
        sa.Column('created', sa.DateTime()),
        sa.Column('updated', sa.DateTime()),
        sa.Column('sip_format', sa.String()),
        sa.Column('content', sa.Text()),
    )

    SIPMetadataType = sa.Table(
        'sipstore_sipmetadatatype',
        metadata,
        sa.Column('id', sa.Integer()),
        sa.Column('title', sa.String()),
        sa.Column('name', sa.String()),
        sa.Column('format', sa.String()),
        sa.Column('schema', sa.String()),
    )

    SIPMetadata = sa.Table(
        'sipstore_sipmetadata',
        metadata,
        sa.Column('created', sa.DateTime()),
        sa.Column('updated', sa.DateTime()),
        sa.Column('sip_id', sqlalchemy_utils.types.uuid.UUIDType()),
        sa.Column('type_id', sa.Integer()),
        sa.Column('content', sa.Text()),
    )

    # Only this kind of connection can return results
    conn = op.get_bind()

    sip_metadata_types_defined = \
        sa.select([sa.func.count()]).select_from(SIPMetadataType)
    if conn.execute(sip_metadata_types_defined).scalar() == 0:
        # Autogenerate SIP metadata types from the available "SIP.sip_format"
        # NOTE: This is a slow operation because of the distinct query. If it's
        # possible beforehand to properly create your SIP metadata type entries
        # it would save some time. Keep in mind that types will have to be
        # created for ALL the values that `sipstore_sip.sip_format` has.
        for (sip_format,) in conn.execute(
                sa.select([OldSIP.c.sip_format]).distinct()):
            op.execute(SIPMetadataType.insert().values(
                title=sip_format, name=sip_format, format=sip_format))
        print('Check your SIPMetadataType entries, to possibly update '
              '"title", "name", "format" and "schema" to appropriate values.')

    # Build SIP metatada type name-to-id mapping
    sip_mtypes = dict(iter(conn.execute(
        sa.select([SIPMetadataType.c.name, SIPMetadataType.c.id]))))
    # NOTE: SWITCH/CASE is more efficient than a JOIN on the types table
    sip_metadata_type_mapping = sa.case(sip_mtypes, value=OldSIP.c.sip_format)

    # Migrate old `content` field as separate entry to new SIPMetadata table
    old_sip_metadata = (
        sa.select(
            [OldSIP.c.id, OldSIP.c.created, OldSIP.c.updated,
             sip_metadata_type_mapping, OldSIP.c.content],
            from_obj=OldSIP.outerjoin(SIPMetadata,
                                      OldSIP.c.id == SIPMetadata.c.sip_id))
        .where(sa.and_(OldSIP.c.sip_format.isnot(None),
                       SIPMetadata.c.sip_id.is_(None))))

    # If there is a chunk size defined, move the data in chunks
    chunk_size = int(os.environ.get('SIPSTORE_MIGRATION_CHUNK_SIZE', 0))
    if chunk_size:
        old_sip_metadata = old_sip_metadata.limit(chunk_size)

    insert_to_sip_metadata = SIPMetadata.insert().from_select(
        ['sip_id', 'created', 'updated', 'type_id', 'content'],
        old_sip_metadata)

    total_rows_migrated = 0
    while conn.execute(insert_to_sip_metadata).rowcount and chunk_size:
        total_rows_migrated += chunk_size
        print('{} rows migrated'.format(total_rows_migrated))

    # Add the NOT NULL constraint
    op.alter_column('sipstore_sip', 'archivable', nullable=False)
    op.alter_column('sipstore_sip', 'archived', nullable=False)

    # Drop the old columns from SIP
    op.drop_column('sipstore_sip', 'content')
    op.drop_column('sipstore_sip', 'sip_format')


def downgrade():
    """Downgrade database.

    After this downgrade it's possible to run the previous version of the model
    (the non-extended SIP metadata DB schema).

    Example downgrade plan (assumes new application code is deployed/running):

    1. `inveniomanage alembic downgrade b31cad2f14c7`
    2. Downgrade application code to old model version
    3. Restart running applications (WSGI apps and/or Celery workers)
    4. Upgrade application (to have the alembic recipes available)
    5. `inveniomanage alembic downgrade ad6ee57b71f9`
    6. (Again) downgrade application code to old model version
    """
    metadata = sa.MetaData()

    # Helper tables from old model
    SIPMetadata = sa.Table(
        'sipstore_sipmetadata',
        metadata,
        sa.Column('sip_id', sqlalchemy_utils.types.uuid.UUIDType()),
        sa.Column('type_id', sa.Integer()),
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

    # Add SIP 'sip_format' and 'content' columns without the NULL constraint
    op.add_column(
        'sipstore_sip', sa.Column('sip_format', sa.VARCHAR(length=7)))
    op.add_column('sipstore_sip', sa.Column('content', sa.TEXT()))

    # Remove the NULL constraint from 'archivable' and 'archived'
    op.alter_column('sipstore_sip', 'archivable', nullable=True)
    op.alter_column('sipstore_sip', 'archived', nullable=True)
