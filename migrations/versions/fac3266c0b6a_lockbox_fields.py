"""lockbox fields

Revision ID: fac3266c0b6a
Revises: 8e8644d2624f
Create Date: 2025-10-16 19:47:53.637654

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "fac3266c0b6a"
down_revision = "8e8644d2624f"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("items")}
    existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("items")}

    with op.batch_alter_table("items", schema=None) as batch_op:
        if "address" not in existing_columns:
            batch_op.add_column(sa.Column("address", sa.String(length=255), nullable=True))
        if "code_current" not in existing_columns:
            batch_op.add_column(sa.Column("code_current", sa.String(length=20), nullable=True))
        if "code_previous" not in existing_columns:
            batch_op.add_column(sa.Column("code_previous", sa.String(length=20), nullable=True))
        if "last_action" not in existing_columns:
            batch_op.add_column(sa.Column("last_action", sa.String(length=50), nullable=True))
        if "last_action_at" not in existing_columns:
            batch_op.add_column(sa.Column("last_action_at", sa.DateTime(), nullable=True))
        if "last_action_by_id" not in existing_columns:
            batch_op.add_column(sa.Column("last_action_by_id", sa.Integer(), nullable=True))
        if "assigned_to" not in existing_columns:
            batch_op.add_column(sa.Column("assigned_to", sa.String(length=120), nullable=True))

        if "fk_items_last_action_by" not in existing_fks:
            batch_op.create_foreign_key(
                "fk_items_last_action_by",
                "users",
                ["last_action_by_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("items")}
    existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("items")}

    with op.batch_alter_table("items", schema=None) as batch_op:
        if "fk_items_last_action_by" in existing_fks:
            batch_op.drop_constraint("fk_items_last_action_by", type_="foreignkey")
        if "assigned_to" in existing_columns:
            batch_op.drop_column("assigned_to")
        if "last_action_by_id" in existing_columns:
            batch_op.drop_column("last_action_by_id")
        if "last_action_at" in existing_columns:
            batch_op.drop_column("last_action_at")
        if "last_action" in existing_columns:
            batch_op.drop_column("last_action")
        if "code_previous" in existing_columns:
            batch_op.drop_column("code_previous")
        if "code_current" in existing_columns:
            batch_op.drop_column("code_current")
        if "address" in existing_columns:
            batch_op.drop_column("address")
