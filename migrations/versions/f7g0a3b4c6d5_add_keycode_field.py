"""add keycode field to items table

Revision ID: f7g0a3b4c6d5
Revises: e6f9a2b3c5d4
Create Date: 2025-10-19 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f7g0a3b4c6d5"
down_revision = "e6f9a2b3c5d4"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("items")}
    if "keycode" not in existing_columns:
        op.add_column("items", sa.Column("keycode", sa.String(length=20), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("items")}
    if "keycode" in existing_columns:
        op.drop_column("items", "keycode")
