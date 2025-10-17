"""baseline

Revision ID: 8e8644d2624f
Revises: 
Create Date: 2025-10-16 10:31:25.531873

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8e8644d2624f'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('items') as batch_op:
        batch_op.alter_column(
            'status',
            server_default='Available',     # ✅ add/keep default
            existing_type=sa.String(length=20),
            nullable=False
        )



def downgrade():
    with op.batch_alter_table('items') as batch_op:
        batch_op.alter_column(
            'status',
            server_default=None,            # remove default if downgrading
            existing_type=sa.String(length=20),
            nullable=False
        )
    # ### end Alembic commands ###
