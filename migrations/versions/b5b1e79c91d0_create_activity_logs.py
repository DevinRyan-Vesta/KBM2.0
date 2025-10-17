"""create activity logs table

Revision ID: b5b1e79c91d0
Revises: 2c55229ba6ad
Create Date: 2025-10-16 22:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b5b1e79c91d0"
down_revision = "2c55229ba6ad"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("target_type", sa.String(length=120), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.String(length=255), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
    )
    op.create_index("ix_activity_logs_created_at", "activity_logs", ["created_at"])
    op.create_index("ix_activity_logs_target", "activity_logs", ["target_type", "target_id"])
    op.create_index("ix_activity_logs_user", "activity_logs", ["user_id"])


def downgrade():
    op.drop_index("ix_activity_logs_user", table_name="activity_logs")
    op.drop_index("ix_activity_logs_target", table_name="activity_logs")
    op.drop_index("ix_activity_logs_created_at", table_name="activity_logs")
    op.drop_table("activity_logs")
