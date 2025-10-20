"""create item_checkouts table for tracking individual checkouts

Revision ID: g8h1a4b5c7d6
Revises: f7g0a3b4c6d5
Create Date: 2025-10-19 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "g8h1a4b5c7d6"
down_revision = "f7g0a3b4c6d5"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("item_checkouts"):
        op.create_table(
            "item_checkouts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("item_id", sa.Integer(), nullable=False),
            sa.Column("checked_out_to", sa.String(length=255), nullable=False),
            sa.Column("checked_out_by_id", sa.Integer(), nullable=True),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("purpose", sa.String(length=255), nullable=True),
            sa.Column("assignment_type", sa.String(length=50), nullable=True),
            sa.Column("expected_return_date", sa.DateTime(), nullable=True),
            sa.Column("address", sa.String(length=255), nullable=True),
            sa.Column("checked_out_at", sa.DateTime(), nullable=False),
            sa.Column("checked_in_at", sa.DateTime(), nullable=True),
            sa.Column("checked_in_by_id", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["item_id"], ["items.id"]),
            sa.ForeignKeyConstraint(["checked_out_by_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["checked_in_by_id"], ["users.id"]),
        )
        op.create_index("ix_item_checkouts_item_id", "item_checkouts", ["item_id"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("item_checkouts"):
        indexes = {index["name"] for index in inspector.get_indexes("item_checkouts")}
        if "ix_item_checkouts_item_id" in indexes:
            op.drop_index("ix_item_checkouts_item_id", table_name="item_checkouts")
        op.drop_table("item_checkouts")
