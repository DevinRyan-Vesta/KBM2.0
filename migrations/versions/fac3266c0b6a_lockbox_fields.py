"""lockbox fields

Revision ID: fac3266c0b6a
Revises: 8e8644d2624f
Create Date: 2025-10-16 19:47:53.637654

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fac3266c0b6a'
down_revision = '8e8644d2624f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('items', schema=None) as batch_op:
        # all new columns are nullable to be SQLite-safe
        batch_op.add_column(sa.Column('address', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('code_current', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('code_previous', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('last_action', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('last_action_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('last_action_by_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('assigned_to', sa.String(length=120), nullable=True))

        # 👇 NAME THE FK CONSTRAINT
        batch_op.create_foreign_key(
            'fk_items_last_action_by',   # <-- required name
            'users',                     # referent table
            ['last_action_by_id'],       # local cols
            ['id'],                      # remote cols
            ondelete="SET NULL"          # optional
        )

def downgrade():
    with op.batch_alter_table('items', schema=None) as batch_op:
        # drop FK before dropping the column
        batch_op.drop_constraint('fk_items_last_action_by', type_='foreignkey')
        batch_op.drop_column('assigned_to')
        batch_op.drop_column('last_action_by_id')
        batch_op.drop_column('last_action_at')
        batch_op.drop_column('last_action')
        batch_op.drop_column('code_previous')
        batch_op.drop_column('code_current')
        batch_op.drop_column('address')
        
    # ### end Alembic commands ###
