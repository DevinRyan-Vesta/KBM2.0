"""add item timestamps

Revision ID: 2c55229ba6ad
Revises: fac3266c0b6a
Create Date: 2025-10-16 20:04:30.076374

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2c55229ba6ad'
down_revision = 'fac3266c0b6a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('items', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'created_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP')  # works on SQLite
        ))
        batch_op.add_column(sa.Column(
            'updated_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP')
        ))

def downgrade():
    with op.batch_alter_table('items', schema=None) as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')

    # ### end Alembic commands ###
