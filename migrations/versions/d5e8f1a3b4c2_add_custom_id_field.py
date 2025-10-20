"""add custom_id field to items table

Revision ID: d5e8f1a3b4c2
Revises: c4d7e8f9a2b1
Create Date: 2025-10-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d5e8f1a3b4c2"
down_revision = "c4d7e8f9a2b1"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("items")}
    existing_indexes = {index["name"] for index in inspector.get_indexes("items")}

    if "custom_id" not in existing_columns:
        op.add_column("items", sa.Column("custom_id", sa.String(length=20), nullable=True))
    if "ix_items_custom_id" not in existing_indexes:
        op.create_index("ix_items_custom_id", "items", ["custom_id"], unique=True)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = {index["name"] for index in inspector.get_indexes("items")}
    existing_columns = {col["name"] for col in inspector.get_columns("items")}

    if "ix_items_custom_id" in existing_indexes:
        op.drop_index("ix_items_custom_id", table_name="items")
    if "custom_id" in existing_columns:
        op.drop_column("items", "custom_id")
