"""Add organization_settings table for custom branding

Revision ID: 004
Revises: 003
Create Date: 2026-03-18

"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organization_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_name", sa.String(255), nullable=True),
        sa.Column("logo_filename", sa.String(255), nullable=True),
        sa.Column("logo_object_key", sa.String(500), nullable=True),
        sa.Column("logo_content_type", sa.String(100), nullable=True),
        sa.Column("logo_storage_backend", sa.String(20), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # Insert the singleton row
    op.execute("INSERT INTO organization_settings (id) VALUES (1)")


def downgrade():
    op.drop_table("organization_settings")
