"""baseline

Revision ID: 8e8644d2624f
Revises:
Create Date: 2025-10-16 10:31:25.531873

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8e8644d2624f"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=1200), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("pin_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("name", name="uq_users_name"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)

    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("custom_id", sa.String(length=20), nullable=True),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="available"),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("code_current", sa.String(length=20), nullable=True),
        sa.Column("code_previous", sa.String(length=20), nullable=True),
        sa.Column("key_hook_number", sa.String(length=20), nullable=True),
        sa.Column("unit_number", sa.String(length=50), nullable=True),
        sa.Column("keycode", sa.String(length=20), nullable=True),
        sa.Column("total_copies", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("copies_checked_out", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("checkout_purpose", sa.String(length=255), nullable=True),
        sa.Column("expected_return_date", sa.DateTime(), nullable=True),
        sa.Column("assignment_type", sa.String(length=50), nullable=True),
        sa.Column("sign_subtype", sa.String(length=20), nullable=True),
        sa.Column("piece_type", sa.String(length=20), nullable=True),
        sa.Column("parent_sign_id", sa.Integer(), nullable=True),
        sa.Column("rider_text", sa.String(length=255), nullable=True),
        sa.Column("material", sa.String(length=100), nullable=True),
        sa.Column("condition", sa.String(length=50), nullable=True),
        sa.Column("last_action", sa.String(length=50), nullable=True),
        sa.Column("last_action_at", sa.DateTime(), nullable=True),
        sa.Column("last_action_by_id", sa.Integer(), nullable=True),
        sa.Column("assigned_to", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(
            ["last_action_by_id"],
            ["users.id"],
            name="fk_items_last_action_by",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("custom_id", name="uq_items_custom_id"),
    )
    op.create_index("ix_items_custom_id", "items", ["custom_id"], unique=False)

    op.create_table(
        "item_checkouts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("checked_out_to", sa.String(length=255), nullable=False),
        sa.Column("checked_out_by_id", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("purpose", sa.String(length=255), nullable=True),
        sa.Column("assignment_type", sa.String(length=50), nullable=True),
        sa.Column("expected_return_date", sa.DateTime(), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("checked_out_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("checked_in_at", sa.DateTime(), nullable=True),
        sa.Column("checked_in_by_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["items.id"],
            name="fk_item_checkouts_item_id",
        ),
        sa.ForeignKeyConstraint(
            ["checked_out_by_id"],
            ["users.id"],
            name="fk_item_checkouts_checked_out_by",
        ),
        sa.ForeignKeyConstraint(
            ["checked_in_by_id"],
            ["users.id"],
            name="fk_item_checkouts_checked_in_by",
        ),
    )
    op.create_index("ix_item_checkouts_item_id", "item_checkouts", ["item_id"], unique=False)

    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("target_type", sa.String(length=120), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.String(length=255), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_activity_logs_user_id",
        ),
    )
    op.create_index("ix_activity_logs_user_id", "activity_logs", ["user_id"], unique=False)


def downgrade():
    op.drop_index("ix_activity_logs_user_id", table_name="activity_logs")
    op.drop_table("activity_logs")

    op.drop_index("ix_item_checkouts_item_id", table_name="item_checkouts")
    op.drop_table("item_checkouts")

    op.drop_index("ix_items_custom_id", table_name="items")
    op.drop_table("items")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
