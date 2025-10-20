"""add sign-specific fields to items table

Revision ID: e6f9a2b3c5d4
Revises: d5e8f1a3b4c2
Create Date: 2025-10-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e6f9a2b3c5d4"
down_revision = "d5e8f1a3b4c2"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("items")}

    with op.batch_alter_table("items", schema=None) as batch_op:
        if "sign_subtype" not in existing_columns:
            batch_op.add_column(sa.Column("sign_subtype", sa.String(length=20), nullable=True))
        if "piece_type" not in existing_columns:
            batch_op.add_column(sa.Column("piece_type", sa.String(length=20), nullable=True))
        if "parent_sign_id" not in existing_columns:
            batch_op.add_column(sa.Column("parent_sign_id", sa.Integer(), nullable=True))
        if "rider_text" not in existing_columns:
            batch_op.add_column(sa.Column("rider_text", sa.String(length=255), nullable=True))
        if "material" not in existing_columns:
            batch_op.add_column(sa.Column("material", sa.String(length=100), nullable=True))
        if "condition" not in existing_columns:
            batch_op.add_column(sa.Column("condition", sa.String(length=50), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("items")}

    with op.batch_alter_table("items", schema=None) as batch_op:
        for column in ["condition", "material", "rider_text", "parent_sign_id", "piece_type", "sign_subtype"]:
            if column in existing_columns:
                batch_op.drop_column(column)
