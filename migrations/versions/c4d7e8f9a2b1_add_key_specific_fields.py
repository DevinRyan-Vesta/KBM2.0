"""add key-specific fields to items table

Revision ID: c4d7e8f9a2b1
Revises: b5b1e79c91d0
Create Date: 2025-10-18 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c4d7e8f9a2b1"
down_revision = "b5b1e79c91d0"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("items")}

    with op.batch_alter_table("items", schema=None) as batch_op:
        if "key_hook_number" not in existing_columns:
            batch_op.add_column(sa.Column("key_hook_number", sa.String(length=20), nullable=True))
        if "unit_number" not in existing_columns:
            batch_op.add_column(sa.Column("unit_number", sa.String(length=50), nullable=True))
        if "total_copies" not in existing_columns:
            batch_op.add_column(sa.Column("total_copies", sa.Integer(), nullable=True, server_default="0"))
        if "copies_checked_out" not in existing_columns:
            batch_op.add_column(sa.Column("copies_checked_out", sa.Integer(), nullable=True, server_default="0"))
        if "checkout_purpose" not in existing_columns:
            batch_op.add_column(sa.Column("checkout_purpose", sa.String(length=255), nullable=True))
        if "expected_return_date" not in existing_columns:
            batch_op.add_column(sa.Column("expected_return_date", sa.DateTime(), nullable=True))
        if "assignment_type" not in existing_columns:
            batch_op.add_column(sa.Column("assignment_type", sa.String(length=50), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("items")}

    with op.batch_alter_table("items", schema=None) as batch_op:
        for column in [
            "assignment_type",
            "expected_return_date",
            "checkout_purpose",
            "copies_checked_out",
            "total_copies",
            "unit_number",
            "key_hook_number",
        ]:
            if column in existing_columns:
                batch_op.drop_column(column)
