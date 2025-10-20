"""add contacts properties and smart locks

Revision ID: 1d9e2f3a4b5c
Revises: g8h1a4b5c7d6
Create Date: 2025-10-19 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1d9e2f3a4b5c"
down_revision = "g8h1a4b5c7d6"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("properties"):
        op.create_table(
            "properties",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("type", sa.String(length=50), nullable=False, server_default="single_family"),
            sa.Column("address_line1", sa.String(length=255), nullable=False),
            sa.Column("address_line2", sa.String(length=255), nullable=True),
            sa.Column("city", sa.String(length=120), nullable=True),
            sa.Column("state", sa.String(length=80), nullable=True),
            sa.Column("postal_code", sa.String(length=20), nullable=True),
            sa.Column("country", sa.String(length=80), nullable=True, server_default="USA"),
            sa.Column("latitude", sa.Float(), nullable=True),
            sa.Column("longitude", sa.Float(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if not inspector.has_table("property_units"):
        op.create_table(
            "property_units",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("property_id", sa.Integer(), nullable=False),
            sa.Column("label", sa.String(length=120), nullable=False),
            sa.Column("floor", sa.String(length=50), nullable=True),
            sa.Column("bedrooms", sa.Integer(), nullable=True),
            sa.Column("bathrooms", sa.Numeric(4, 1), nullable=True),
            sa.Column("square_feet", sa.Integer(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["property_id"], ["properties.id"], name="fk_property_units_property_id", ondelete="CASCADE"),
        )
        op.create_index("ix_property_units_property_id", "property_units", ["property_id"])

    if not inspector.has_table("contacts"):
        op.create_table(
            "contacts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("contact_type", sa.String(length=50), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("company", sa.String(length=255), nullable=True),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("phone", sa.String(length=50), nullable=True),
            sa.Column("user_id", sa.Integer(), nullable=True, unique=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_contacts_user_id", ondelete="SET NULL"),
        )
        op.create_index("ix_contacts_email", "contacts", ["email"])

    if not inspector.has_table("smart_locks"):
        op.create_table(
            "smart_locks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("label", sa.String(length=255), nullable=False),
            sa.Column("provider", sa.String(length=120), nullable=True),
            sa.Column("code", sa.String(length=120), nullable=False),
            sa.Column("backup_code", sa.String(length=120), nullable=True),
            sa.Column("instructions", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("property_id", sa.Integer(), nullable=True),
            sa.Column("property_unit_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["property_id"], ["properties.id"], name="fk_smart_locks_property_id", ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["property_unit_id"], ["property_units.id"], name="fk_smart_locks_property_unit_id", ondelete="SET NULL"),
        )
        op.create_index("ix_smart_locks_property_id", "smart_locks", ["property_id"])
        op.create_index("ix_smart_locks_property_unit_id", "smart_locks", ["property_unit_id"])

    existing_columns = {col["name"] for col in inspector.get_columns("items")}
    existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("items")}

    with op.batch_alter_table("items", schema=None) as batch_op:
        if "property_id" not in existing_columns:
            batch_op.add_column(sa.Column("property_id", sa.Integer(), nullable=True))
        if "property_unit_id" not in existing_columns:
            batch_op.add_column(sa.Column("property_unit_id", sa.Integer(), nullable=True))
        if "fk_items_property_id" not in existing_fks:
            batch_op.create_foreign_key(
                "fk_items_property_id",
                "properties",
                ["property_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if "fk_items_property_unit_id" not in existing_fks:
            batch_op.create_foreign_key(
                "fk_items_property_unit_id",
                "property_units",
                ["property_unit_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("items")}
    existing_columns = {col["name"] for col in inspector.get_columns("items")}

    with op.batch_alter_table("items", schema=None) as batch_op:
        if "fk_items_property_unit_id" in existing_fks:
            batch_op.drop_constraint("fk_items_property_unit_id", type_="foreignkey")
        if "fk_items_property_id" in existing_fks:
            batch_op.drop_constraint("fk_items_property_id", type_="foreignkey")
        if "property_unit_id" in existing_columns:
            batch_op.drop_column("property_unit_id")
        if "property_id" in existing_columns:
            batch_op.drop_column("property_id")

    if inspector.has_table("smart_locks"):
        indexes = {index["name"] for index in inspector.get_indexes("smart_locks")}
        if "ix_smart_locks_property_unit_id" in indexes:
            op.drop_index("ix_smart_locks_property_unit_id", table_name="smart_locks")
        if "ix_smart_locks_property_id" in indexes:
            op.drop_index("ix_smart_locks_property_id", table_name="smart_locks")
        op.drop_table("smart_locks")

    if inspector.has_table("contacts"):
        indexes = {index["name"] for index in inspector.get_indexes("contacts")}
        if "ix_contacts_email" in indexes:
            op.drop_index("ix_contacts_email", table_name="contacts")
        op.drop_table("contacts")

    if inspector.has_table("property_units"):
        indexes = {index["name"] for index in inspector.get_indexes("property_units")}
        if "ix_property_units_property_id" in indexes:
            op.drop_index("ix_property_units_property_id", table_name="property_units")
        op.drop_table("property_units")

    if inspector.has_table("properties"):
        op.drop_table("properties")
